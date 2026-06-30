"""Polling scheduler with per-stock queue, exponential backoff, and trading calendar."""

from __future__ import annotations

import datetime as dt
import random
from typing import Optional

from stock_watcher.config import BackoffConfig
from stock_watcher.models import Market

# ---------------------------------------------------------------------------
# Trading schedules
# ---------------------------------------------------------------------------

TRADING_SCHEDULES = {
    "a_share": [
        (dt.time(9, 30), dt.time(11, 30)),   # morning session
        (dt.time(13, 0), dt.time(15, 0)),     # afternoon session
    ],
    "hk": [
        (dt.time(9, 30), dt.time(12, 0)),     # morning session
        (dt.time(13, 0), dt.time(16, 0)),     # afternoon session
    ],
}

CST = dt.timezone(dt.timedelta(hours=8))  # China Standard Time (UTC+8)


def _now_cst() -> dt.datetime:
    """Return current time in China Standard Time."""
    return dt.datetime.now(CST)


def _is_weekday(t: dt.datetime) -> bool:
    """Return True if t is Mon-Fri."""
    return t.weekday() < 5  # 0=Mon … 4=Fri


def _is_in_any_session(t: dt.datetime, sessions: list[tuple[dt.time, dt.time]]) -> bool:
    """Return True if t falls within any of the given (start, end) time windows."""
    current_time = t.time()
    for start, end in sessions:
        if start <= current_time < end:
            return True
    return False


def is_a_share_trading_time(t: Optional[dt.datetime] = None) -> bool:
    """Return True if now (or *t*) is during A-share trading hours."""
    if t is None:
        t = _now_cst()
    return _is_weekday(t) and _is_in_any_session(t, TRADING_SCHEDULES["a_share"])


def is_hk_trading_time(t: Optional[dt.datetime] = None) -> bool:
    """Return True if now (or *t*) is during HK trading hours."""
    if t is None:
        t = _now_cst()
    return _is_weekday(t) and _is_in_any_session(t, TRADING_SCHEDULES["hk"])


def is_any_market_open(t: Optional[dt.datetime] = None) -> bool:
    """Return True if any monitored market is currently open."""
    return is_a_share_trading_time(t) or is_hk_trading_time(t)


# ---------------------------------------------------------------------------
# TradingCalendar
# ---------------------------------------------------------------------------


class TradingCalendar:
    """Tells whether a given stock code is in a trading window right now."""

    def is_trading(self, code: str, at: Optional[dt.datetime] = None) -> bool:
        """Return True if the market for *code* is currently trading."""
        if at is None:
            at = _now_cst()
        try:
            market = Market.from_code(code)
        except ValueError:
            return False

        if market in (Market.SHANGHAI, Market.SHENZHEN):
            return is_a_share_trading_time(at)
        return is_hk_trading_time(at)

    def status_string(self, at: Optional[dt.datetime] = None) -> str:
        """Return a human-readable status for the current time."""
        if at is None:
            at = _now_cst()

        a_open = is_a_share_trading_time(at)
        hk_open = is_hk_trading_time(at)

        if a_open and hk_open:
            return "A股/港股 交易中"
        elif a_open:
            return "A股交易中 · 港股休市"
        elif hk_open:
            return "港股交易中 · A股休市"
        else:
            return "休市"


# ---------------------------------------------------------------------------
# BackoffController
# ---------------------------------------------------------------------------


class BackoffController:
    """Exponential backoff with jitter for failed requests."""

    def __init__(
        self, base: float = 5.0, max_delay: float = 120.0, multiplier: float = 2.0
    ) -> None:
        self._base = base
        self._max = max_delay
        self._multiplier = multiplier
        self._failures: int = 0

    @classmethod
    def from_config(cls, config: "BackoffConfig") -> "BackoffController":
        """Create a BackoffController from a BackoffConfig."""
        return cls(
            base=config.base,
            max_delay=config.max_delay,
            multiplier=config.multiplier,
        )

    @property
    def consecutive_failures(self) -> int:
        return self._failures

    @property
    def current_delay(self) -> float:
        """The raw (unjittered) current backoff delay."""
        return min(self._base * (self._multiplier ** self._failures), self._max)

    @property
    def is_backed_off(self) -> bool:
        return self._failures > 0

    def backoff(self) -> None:
        """Increment the failure counter, increasing the delay."""
        self._failures += 1

    def reset(self) -> None:
        """Reset the failure counter to zero (e.g. after a successful request)."""
        self._failures = 0

    def get_delay(self) -> float:
        """Return the current backoff delay with ±25% jitter applied."""
        raw = self.current_delay
        jitter = raw * 0.25 * (random.random() * 2 - 1)  # ±25%
        return raw + jitter


# ---------------------------------------------------------------------------
# PollQueue
# ---------------------------------------------------------------------------


class PollQueue:
    """Round-robin queue that cycles through stock codes for polling."""

    def __init__(self, codes: list[str]) -> None:
        self._codes: list[str] = list(codes)
        self._index: int = 0

    @property
    def size(self) -> int:
        return len(self._codes)

    @property
    def all_codes(self) -> list[str]:
        """Return a copy of all codes currently in the queue."""
        return list(self._codes)

    def next(self) -> Optional[str]:
        """Return the next stock code to poll, or None if the queue is empty."""
        if not self._codes:
            return None
        code = self._codes[self._index]
        self._index = (self._index + 1) % len(self._codes)
        return code

    def add(self, code: str) -> None:
        """Add a stock code to the queue (no-op if already present)."""
        if code not in self._codes:
            self._codes.append(code)

    def remove(self, code: str) -> None:
        """Remove a stock code from the queue."""
        if code in self._codes:
            idx = self._codes.index(code)
            self._codes.remove(code)
            # Adjust index so we don't skip the next element
            if self._codes and idx < self._index:
                self._index -= 1
            elif self._codes:
                self._index = self._index % len(self._codes)

    def has(self, code: str) -> bool:
        """Return True if the code is in the queue."""
        return code in self._codes
