"""HTTP fetchers for Sina (A-share) and Tencent (HK) real-time quote APIs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from stock_watcher.config import RequestConfig
from stock_watcher.models import Market, StockQuote


# ---------------------------------------------------------------------------
# FetchError
# ---------------------------------------------------------------------------


class FetchError(Exception):
    """Raised when a stock quote fetch fails."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code

    @property
    def is_retryable(self) -> bool:
        """Return True if the error is transient and worth retrying."""
        if self.status_code is None:
            # timeout / network error → retryable
            return True
        # 429, 5xx → retryable; 4xx (except 429) → not retryable
        return self.status_code == 429 or self.status_code >= 500


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def parse_sina_response(code: str, text: str) -> StockQuote:
    """Parse a Sina Finance real-time quote response.

    Format: ``var hq_str_<code>="name,open,prev_close,price,high,low,...";``

    Field indices (0-based):
      0: name
      1: today open
      2: previous close
      3: current price
      4: today high
      5: today low
      …
    change_pct and change_amount are derived from price vs previous close.
    """
    try:
        text = text.strip()
        if not text:
            return StockQuote(code=code)

        # Extract the quoted CSV portion
        start = text.index('="') + 2
        end = text.index('";', start) if '";' in text else len(text)
        quoted = text[start:end]

        fields = quoted.split(",")
        if len(fields) < 6:
            return StockQuote(code=code)

        name = fields[0]
        prev_close = _parse_float(fields[2])
        price = _parse_float(fields[3])
        high = _parse_float(fields[4])
        low = _parse_float(fields[5])

        change_pct = _calc_pct(price, prev_close)
        change_amount = _calc_amount(price, prev_close)

        return StockQuote(
            code=code,
            name=name,
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            high=high,
            low=low,
        )
    except (ValueError, IndexError):
        return StockQuote(code=code)


def parse_tencent_response(code: str, text: str) -> StockQuote:
    """Parse a Tencent Finance real-time quote response for HK stocks.

    Format: ``v_<code>="<fields separated by ~>"``

    Field indices (0-based, ~ delimited):
      1: name
      3: current price
      4: yesterday close
      5: open
      6: change amount (volume in some versions, but 6=amount in v2)
      31: change pct
      33: high
      34: low

    We extract: name(1), price(3), high(33), low(34).
    change_pct from field 31, change_amount from field 6 or derived.
    """
    try:
        text = text.strip()
        if not text:
            return StockQuote(code=code)

        # Extract the quoted ~-delimited portion
        start = text.index('="') + 2
        end = text.index('";', start) if '";' in text else len(text)
        quoted = text[start:end]

        fields = quoted.split("~")
        if len(fields) < 35:
            return StockQuote(code=code)

        name = fields[1]
        price = _parse_float(fields[3])
        prev_close = _parse_float(fields[4])
        high = _parse_float(fields[33])
        low = _parse_float(fields[34])
        change_amount = _parse_float(fields[6])
        change_pct = _parse_float(fields[32]) if len(fields) > 32 else None

        # Fallback: derive from price vs prev close if direct fields are None
        if change_pct is None:
            change_pct = _calc_pct(price, prev_close)
        if change_amount is None:
            change_amount = _calc_amount(price, prev_close)

        return StockQuote(
            code=code,
            name=name,
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            high=high,
            low=low,
        )
    except (ValueError, IndexError):
        return StockQuote(code=code)


# ---------------------------------------------------------------------------
# Fetcher base & implementations
# ---------------------------------------------------------------------------


class Fetcher(ABC):
    """Abstract base for stock quote fetchers."""

    def __init__(self, request_config: RequestConfig) -> None:
        self._config = request_config

    @abstractmethod
    async def fetch(self, code: str) -> StockQuote:
        """Fetch a quote for the given stock code."""


class SinaFetcher(Fetcher):
    """Fetcher for A-share stocks using Sina Finance API."""

    BASE_URL = "https://hq.sinajs.cn/list={code}"

    async def fetch(self, code: str) -> StockQuote:
        url = self.BASE_URL.format(code=code)
        client = httpx.AsyncClient(timeout=self._config.timeout)
        try:
            headers = {
                "User-Agent": self._config.get_random_ua(),
                "Referer": "https://finance.sina.com.cn/",
            }
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise FetchError(
                    f"HTTP {resp.status_code}", code=code, status_code=resp.status_code
                )
            return parse_sina_response(code, resp.text)
        except httpx.TimeoutException:
            raise FetchError("timeout", code=code)
        except FetchError:
            raise
        finally:
            await client.aclose()


class TencentFetcher(Fetcher):
    """Fetcher for HK stocks using Tencent Finance API."""

    BASE_URL = "https://qt.gtimg.cn/q={code}"

    async def fetch(self, code: str) -> StockQuote:
        url = self.BASE_URL.format(code=code)
        client = httpx.AsyncClient(timeout=self._config.timeout)
        try:
            headers = {
                "User-Agent": self._config.get_random_ua(),
                "Referer": "https://gu.qq.com/",
            }
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise FetchError(
                    f"HTTP {resp.status_code}", code=code, status_code=resp.status_code
                )
            return parse_tencent_response(code, resp.text)
        except httpx.TimeoutException:
            raise FetchError("timeout", code=code)
        except FetchError:
            raise
        finally:
            await client.aclose()


def get_fetcher(code: str, request_config: Optional[RequestConfig] = None) -> Fetcher:
    """Factory: return the correct Fetcher for a given stock code."""
    if request_config is None:
        request_config = RequestConfig()

    market = Market.from_code(code)
    if market in (Market.SHANGHAI, Market.SHENZHEN):
        return SinaFetcher(request_config)
    elif market == Market.HONGKONG:
        return TencentFetcher(request_config)
    raise ValueError(f"Unknown market prefix for code {code!r}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_float(s: str) -> Optional[float]:
    """Parse a string to float; return None on failure."""
    if not s or s.strip() == "":
        return None
    try:
        return float(s.strip())
    except ValueError:
        return None


def _calc_pct(price: Optional[float], prev_close: Optional[float]) -> Optional[float]:
    """Compute change percentage from price and previous close."""
    if price is None or prev_close is None or prev_close == 0:
        return None
    return round((price - prev_close) / prev_close * 100, 2)


def _calc_amount(price: Optional[float], prev_close: Optional[float]) -> Optional[float]:
    """Compute change amount from price and previous close."""
    if price is None or prev_close is None:
        return None
    return round(price - prev_close, 2)
