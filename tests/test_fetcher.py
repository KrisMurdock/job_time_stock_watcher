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
)
from stock_watcher.models import StockQuote
from stock_watcher.config import RequestConfig


# ---------------------------------------------------------------------------
# parse_sina_response
# ---------------------------------------------------------------------------
class TestParseSinaResponse:
    def test_parse_valid_shanghai(self):
        """Real Sina response format for A-share."""
        text = 'var hq_str_sh000001="上证指数,3250.60,3240.00,3260.00,40.10,1.25,3240.00,3260.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";'
        quote = parse_sina_response("sh000001", text)
        assert quote.code == "sh000001"
        assert quote.name == "上证指数"
        assert quote.price == 3250.60
        assert quote.change_pct == 1.25
        assert quote.change_amount == 40.10
        assert quote.high == 3260.00
        assert quote.low == 3240.00

    def test_parse_valid_shenzhen(self):
        text = 'var hq_str_sz000001="平安银行,12.50,12.40,12.60,-1.20,-0.15,12.40,12.60,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";'
        quote = parse_sina_response("sz000001", text)
        assert quote.code == "sz000001"
        assert quote.name == "平安银行"
        assert quote.price == 12.50
        assert quote.change_pct == -1.20
        assert quote.change_amount == -0.15
        assert quote.high == 12.60
        assert quote.low == 12.40

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
        text = '  var hq_str_sh000001="上证指数,3250.60,3240.00,3260.00,40.10,1.25,3240.00,3260.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";  '
        quote = parse_sina_response("sh000001", text)
        assert quote.is_valid
        assert quote.price == 3250.60


# ---------------------------------------------------------------------------
# parse_tencent_response
# ---------------------------------------------------------------------------
class TestParseTencentResponse:
    def test_parse_valid_hk_stock(self):
        """Real Tencent response format for HK stock."""
        text = 'v_hk00700="1~腾讯控股~00700~385.600~390.000~382.400~5.200~1.37~385.600~385.800~385.600~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~";'
        quote = parse_tencent_response("hk00700", text)
        assert quote.code == "hk00700"
        assert quote.name == "腾讯控股"
        assert quote.price == 385.60
        assert quote.change_pct == 1.37
        assert quote.change_amount == 5.20
        assert quote.high == 390.00
        assert quote.low == 382.40

    def test_parse_negative_change(self):
        text = 'v_hk00700="1~腾讯控股~00700~380.000~385.000~375.000~-5.000~-1.30~380.000~380.500~380.000~0~0~...~";'
        quote = parse_tencent_response("hk00700", text)
        assert quote.change_pct == -1.30
        assert quote.change_amount == -5.00

    def test_parse_empty_response(self):
        quote = parse_tencent_response("hk00700", "")
        assert not quote.is_valid

    def test_parse_wrong_code_in_response(self):
        """Parser should still work — code is from the request, not the response."""
        text = 'v_hk00001="1~长和~00001~50.000~...' + '~' * 50 + '";'
        quote = parse_tencent_response("hk00700", text)
        # The function extracts data from whatever quote is in the response
        # Code in the returned quote comes from the parameter, not the text
        assert quote.code == "hk00700"
        assert quote.name == "长和"


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

    def test_raises_for_unknown_prefix(self):
        with pytest.raises(ValueError):
            get_fetcher("usAAPL")


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
# Fetcher integration with respx (mocked HTTP)
# ---------------------------------------------------------------------------
class TestSinaFetcherIntegration:
    @pytest.mark.asyncio
    async def test_fetch_success(self, respx_mock):
        respx_mock.get("https://hq.sinajs.cn/list=sh000001").mock(
            return_value=httpx.Response(
                200,
                text='var hq_str_sh000001="上证指数,3250.60,3240.00,3260.00,40.10,1.25,3240.00,3260.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";',
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
        respx_mock.get("https://qt.gtimg.cn/q=hk00700").mock(
            return_value=httpx.Response(
                200,
                text='v_hk00700="1~腾讯控股~00700~385.600~390.000~382.400~5.200~1.37~385.600~385.800~385.600~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~";',
            )
        )

        fetcher = TencentFetcher(RequestConfig(timeout=10, user_agent_pool=["Test-UA"]))
        quote = await fetcher.fetch("hk00700")
        assert quote.code == "hk00700"
        assert quote.name == "腾讯控股"
        assert quote.price == 385.60
