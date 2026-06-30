"""Unit tests for stock_watcher.fetcher — HTTP fetching and response parsing."""

import pytest
import respx
import httpx

from stock_watcher.fetcher import (
    Fetcher,
    SinaFetcher,
    TencentFetcher,
    get_fetcher,
    parse_sina_response,
    parse_tencent_response,
    FetchError,
    search_stocks,
)
from stock_watcher.models import StockQuote
from stock_watcher.config import RequestConfig


# ---------------------------------------------------------------------------
# parse_sina_response
# ---------------------------------------------------------------------------
class TestParseSinaResponse:
    def test_parse_valid_shanghai(self):
        """Real Sina response format for A-share: name,open,prev_close,price,high,low,…"""
        # open=3240.00, prev_close=3200.00, price=3250.60, high=3260.00, low=3201.00
        # change_pct = (3250.60-3200)/3200*100 ≈ 1.58
        # change_amount = 3250.60-3200 = 50.60
        text = 'var hq_str_sh000001="上证指数,3240.00,3200.00,3250.60,3260.00,3201.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";'
        quote = parse_sina_response("sh000001", text)
        assert quote.code == "sh000001"
        assert quote.name == "上证指数"
        assert quote.price == 3250.60
        assert quote.change_pct == pytest.approx(1.58, abs=0.01)
        assert quote.change_amount == 50.60
        assert quote.high == 3260.00
        assert quote.low == 3201.00

    def test_parse_valid_shenzhen(self):
        # open=12.40, prev_close=12.50, price=12.20, high=12.60, low=12.10
        # change_pct = (12.20-12.50)/12.50*100 = -2.40
        # change_amount = 12.20-12.50 = -0.30
        text = 'var hq_str_sz000001="平安银行,12.40,12.50,12.20,12.60,12.10,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";'
        quote = parse_sina_response("sz000001", text)
        assert quote.code == "sz000001"
        assert quote.name == "平安银行"
        assert quote.price == 12.20
        assert quote.change_pct == -2.40
        assert quote.change_amount == -0.30
        assert quote.high == 12.60
        assert quote.low == 12.10

    def test_parse_empty_response_returns_invalid_quote(self):
        text = ""
        quote = parse_sina_response("sh000001", text)
        assert quote.code == "sh000001"
        assert not quote.is_valid

    def test_parse_malformed_response_no_equals(self):
        text = "garbage without equals"
        quote = parse_sina_response("sh000001", text)
        assert not quote.is_valid

    def test_parse_malformed_response_insufficient_fields(self):
        text = 'var hq_str_sh000001="name,price";'
        quote = parse_sina_response("sh000001", text)
        assert not quote.is_valid

    def test_parse_with_leading_trailing_whitespace(self):
        text = '  var hq_str_sh000001="上证指数,3240.00,3200.00,3250.60,3260.00,3201.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";  '
        quote = parse_sina_response("sh000001", text)
        assert quote.is_valid
        assert quote.price == 3250.60


# ---------------------------------------------------------------------------
# parse_tencent_response
# ---------------------------------------------------------------------------
class TestParseTencentResponse:
    def test_parse_valid_hk_stock(self):
        """Real Tencent response format for HK stock.
        Field indices: 0=market, 1=name, 2=code,
        3=price, 4=prev_close, 5=open, 6=volume,
        … 31=change_amount, 32=change_pct, 33=high, 34=low
        """
        # Build a 60-field ~-delimited string with known values at the right positions
        fields = [""] * 60
        fields[1] = "腾讯控股"        # name
        fields[3] = "385.600"        # price
        fields[4] = "390.000"        # prev_close
        fields[5] = "382.400"        # open
        fields[31] = "5.200"         # change_amount
        fields[32] = "1.37"          # change_pct
        fields[33] = "392.000"       # high
        fields[34] = "380.000"       # low
        text = 'v_hk00700="' + "~".join(fields) + '";'
        quote = parse_tencent_response("hk00700", text)
        assert quote.code == "hk00700"
        assert quote.name == "腾讯控股"
        assert quote.price == 385.60
        assert quote.change_pct == 1.37
        assert quote.change_amount == 5.20
        assert quote.high == 392.00
        assert quote.low == 380.00

    def test_parse_negative_change(self):
        # price=380, prev_close=385, change_amount=-5.00, change_pct=-1.30
        fields = [""] * 60
        fields[1] = "腾讯控股"
        fields[3] = "380.000"
        fields[4] = "385.000"
        fields[5] = "375.000"
        fields[31] = "-5.000"
        fields[32] = "-1.30"
        fields[33] = "390.000"
        fields[34] = "375.000"
        text = 'v_hk00700="' + "~".join(fields) + '";'
        quote = parse_tencent_response("hk00700", text)
        assert quote.change_pct == -1.30
        assert quote.change_amount == -5.00

    def test_parse_empty_response(self):
        quote = parse_tencent_response("hk00700", "")
        assert not quote.is_valid

    def test_parse_wrong_code_in_response(self):
        """Parser should still work — code is from the parameter, not the response."""
        fields = [""] * 60
        fields[1] = "长和"
        fields[3] = "50.000"
        fields[4] = "50.000"
        text = 'v_hk00001="' + "~".join(fields) + '";'
        quote = parse_tencent_response("hk00700", text)
        assert quote.code == "hk00700"
        assert quote.name == "长和"


# ---------------------------------------------------------------------------
# parse_sina_us_response
# ---------------------------------------------------------------------------
class TestParseSinaUsResponse:
    """Tests for parse_sina_us_response — Sina gb_ API for US stocks."""

    # fmt: off
    _SAMPLE = (
        'var hq_str_gb_aapl='
        '"苹果,281.7400,-0.72,2026-06-30 17:00:16,-2.0400,286.7300,'
        '288.3697,279.8500,317.4000,200.4500,66427002,79974263,,'
        '8.30,33.940000,0.00,0.00,0.27,0.00,14687354038,63,'
        '280.8180,-0.33,-0.92,Jun 30 05:00AM EDT,Jun 29 04:00PM EDT,'
        '283.7800,52351,1,2026"'
    )
    # fmt: on

    def test_parse_valid_us_stock(self):
        from stock_watcher.fetcher import parse_sina_us_response

        quote = parse_sina_us_response("usaapl", self._SAMPLE)
        assert quote.code == "usaapl"
        assert quote.name == "苹果"
        assert quote.price == pytest.approx(281.74, abs=0.01)
        assert quote.change_pct == pytest.approx(-0.72, abs=0.01)
        assert quote.change_amount == pytest.approx(-2.04, abs=0.01)
        assert quote.high == pytest.approx(286.73, abs=0.01)
        assert quote.low == pytest.approx(279.85, abs=0.01)

    def test_parse_empty_response(self):
        from stock_watcher.fetcher import parse_sina_us_response

        quote = parse_sina_us_response("usaapl", "")
        assert quote.code == "usaapl"
        assert not quote.is_valid

    def test_parse_insufficient_fields(self):
        from stock_watcher.fetcher import parse_sina_us_response

        quote = parse_sina_us_response("usaapl", 'var hq_str_gb_aapl="a,b,c"')
        assert not quote.is_valid


# ---------------------------------------------------------------------------
# get_fetcher
# ---------------------------------------------------------------------------
class TestGetFetcher:
    def test_returns_sina_for_sh(self):
        f = get_fetcher("sh000001")
        assert isinstance(f, SinaFetcher)

    def test_returns_sina_for_sz(self):
        f = get_fetcher("sz000001")
        assert isinstance(f, SinaFetcher)

    def test_returns_tencent_for_hk(self):
        f = get_fetcher("hk00700")
        assert isinstance(f, TencentFetcher)

    def test_returns_sina_for_us(self):
        f = get_fetcher("usaapl")
        assert isinstance(f, SinaFetcher)

    def test_raises_for_unknown_prefix(self):
        with pytest.raises(ValueError):
            get_fetcher("xx12345")


# ---------------------------------------------------------------------------
# FetchError
# ---------------------------------------------------------------------------
class TestFetchError:
    def test_create_with_message_and_code(self):
        e = FetchError("timeout", code="sh000001")
        assert str(e) == "timeout"
        assert e.code == "sh000001"

    def test_is_retryable_timeout(self):
        e = FetchError("timeout", code="sh000001")
        assert e.is_retryable is True

    def test_is_retryable_http_429(self):
        e = FetchError("HTTP 429", code="sh000001", status_code=429)
        assert e.is_retryable is True

    def test_is_retryable_http_503(self):
        e = FetchError("HTTP 503", code="sh000001", status_code=503)
        assert e.is_retryable is True

    def test_non_retryable_http_404(self):
        e = FetchError("HTTP 404", code="sh000001", status_code=404)
        assert e.is_retryable is False

    def test_non_retryable_http_400(self):
        e = FetchError("Bad request", code="sh000001", status_code=400)
        assert e.is_retryable is False


# ---------------------------------------------------------------------------
# search_stocks
# ---------------------------------------------------------------------------


class TestParseSuggestResponse:
    """Parse Sina suggest API response."""

    def test_parse_valid_response(self):
        from stock_watcher.fetcher import _parse_suggest_response
        # Real API format: name,market_type,raw_code,prefixed_code,name_repeat,...
        text = 'var suggestvalue="平安银行,12,000001,sz000001,平安银行;腾讯控股,31,00700,00700,腾讯控股;浦发银行,11,600000,sh600000,浦发银行";'
        results = _parse_suggest_response(text)
        assert len(results) == 3
        assert results[0].code == "sz000001"
        assert results[0].name == "平安银行"
        assert results[0].market == "sz"
        assert results[1].code == "hk00700"
        assert results[1].name == "腾讯控股"
        assert results[1].market == "hk"
        assert results[2].code == "sh600000"
        assert results[2].name == "浦发银行"
        assert results[2].market == "sh"

    def test_parse_empty_response(self):
        from stock_watcher.fetcher import _parse_suggest_response
        assert _parse_suggest_response("") == []

    def test_parse_no_results(self):
        from stock_watcher.fetcher import _parse_suggest_response
        text = 'var suggestvalue="";'
        assert _parse_suggest_response(text) == []

    def test_parse_unknown_market_skipped(self):
        from stock_watcher.fetcher import _parse_suggest_response
        text = 'var suggestvalue="苹果,99,AAPL,AAPL,苹果;平安,12,000001,sz000001,平安";'
        results = _parse_suggest_response(text)
        # Only the second entry (market 12 → sz) should be included
        assert len(results) == 1
        assert results[0].code == "sz000001"

    def test_parse_malformed_returns_empty(self):
        from stock_watcher.fetcher import _parse_suggest_response
        assert _parse_suggest_response("garbage") == []


class TestSearchStocks:
    """Integration tests for search_stocks (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, respx_mock):
        respx_mock.get("https://suggest3.sinajs.cn/suggest/type=11,12,31,14,15&key=腾讯").mock(
            return_value=httpx.Response(
                200,
                text='var suggestvalue="腾讯控股,31,00700,00700,腾讯控股;平安银行,12,000001,sz000001,平安银行";',
            )
        )
        results = await search_stocks("腾讯")
        assert len(results) == 2
        assert results[0].code == "hk00700"
        assert results[0].name == "腾讯控股"

    @pytest.mark.asyncio
    async def test_search_no_results(self, respx_mock):
        respx_mock.get("https://suggest3.sinajs.cn/suggest/type=11,12,31,14,15&key=zzzz").mock(
            return_value=httpx.Response(200, text='var suggestvalue="";')
        )
        results = await search_stocks("zzzz")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, respx_mock):
        respx_mock.get("https://suggest3.sinajs.cn/suggest/type=11,12,31,14,15&key=test").mock(
            return_value=httpx.Response(500)
        )
        results = await search_stocks("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_timeout(self, respx_mock):
        respx_mock.get("https://suggest3.sinajs.cn/suggest/type=11,12,31,14,15&key=test").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        results = await search_stocks("test")
        assert results == []


# ---------------------------------------------------------------------------
# Fetcher integration with respx (mocked HTTP)
# ---------------------------------------------------------------------------
class TestSinaFetcherIntegration:
    @pytest.mark.asyncio
    async def test_fetch_success(self, respx_mock):
        respx_mock.get("https://hq.sinajs.cn/list=sh000001").mock(
            return_value=httpx.Response(
                200,
                text='var hq_str_sh000001="上证指数,3240.00,3200.00,3250.60,3260.00,3201.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";',
            )
        )

        fetcher = SinaFetcher(RequestConfig(timeout=10, user_agent_pool=["Test-UA"]))
        quote = await fetcher.fetch("sh000001")
        assert quote.code == "sh000001"
        assert quote.name == "上证指数"
        assert quote.price == 3250.60

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, respx_mock):
        respx_mock.get("https://hq.sinajs.cn/list=sh000001").mock(
            return_value=httpx.Response(500)
        )

        fetcher = SinaFetcher(RequestConfig(timeout=10, user_agent_pool=["Test-UA"]))
        with pytest.raises(FetchError) as exc:
            await fetcher.fetch("sh000001")
        assert exc.value.status_code == 500
        assert exc.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_fetch_timeout(self, respx_mock):
        respx_mock.get("https://hq.sinajs.cn/list=sh000001").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        fetcher = SinaFetcher(RequestConfig(timeout=10, user_agent_pool=["Test-UA"]))
        with pytest.raises(FetchError) as exc:
            await fetcher.fetch("sh000001")
        assert exc.value.is_retryable is True


class TestTencentFetcherIntegration:
    @pytest.mark.asyncio
    async def test_fetch_success(self, respx_mock):
        fields = [""] * 60
        fields[1] = "腾讯控股"
        fields[3] = "385.600"
        fields[4] = "390.000"
        fields[31] = "5.200"
        fields[32] = "1.37"
        fields[33] = "392.000"
        fields[34] = "380.000"
        respx_mock.get("https://qt.gtimg.cn/q=hk00700").mock(
            return_value=httpx.Response(
                200,
                text='v_hk00700="' + "~".join(fields) + '";',
            )
        )

        fetcher = TencentFetcher(RequestConfig(timeout=10, user_agent_pool=["Test-UA"]))
        quote = await fetcher.fetch("hk00700")
        assert quote.code == "hk00700"
        assert quote.name == "腾讯控股"
        assert quote.price == 385.60
