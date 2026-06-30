"""Unit tests for stock_watcher.models."""

import pytest
from stock_watcher.models import Market, StockQuote, WatchlistItem, AlertRule, AlertType


class TestMarket:
    """Market enum — distinguishes A-share (Shanghai/Shenzhen) from HK."""

    def test_shanghai_prefix_sh(self):
        """sh000001 → Market.SHANGHAI"""
        assert Market.from_code("sh000001") == Market.SHANGHAI

    def test_shenzhen_prefix_sz(self):
        """sz000001 → Market.SHENZHEN"""
        assert Market.from_code("sz000001") == Market.SHENZHEN

    def test_hongkong_prefix_hk(self):
        """hk00700 → Market.HONGKONG"""
        assert Market.from_code("hk00700") == Market.HONGKONG

    def test_unknown_prefix_raises(self):
        """Unknown prefix (e.g. 'xx12345') raises ValueError."""
        with pytest.raises(ValueError, match="Unknown market prefix"):
            Market.from_code("xx12345")

    def test_empty_code_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="code"):
            Market.from_code("")

    def test_code_too_short_raises(self):
        """Code shorter than 2 chars raises ValueError."""
        with pytest.raises(ValueError, match="code"):
            Market.from_code("s")

    def test_is_valid_code(self):
        """is_valid_code returns True/False without raising."""
        assert Market.is_valid_code("sh000001") is True
        assert Market.is_valid_code("sz399001") is True
        assert Market.is_valid_code("hk00700") is True
        assert Market.is_valid_code("usaapl") is True
        assert Market.is_valid_code("") is False


class TestStockQuote:
    """Immutable value object for a single price snapshot."""

    def test_create_quote_with_all_fields(self):
        q = StockQuote(
            code="sh000001",
            name="上证指数",
            price=3250.60,
            change_pct=1.25,
            change_amount=40.10,
            high=3260.00,
            low=3240.00,
        )
        assert q.code == "sh000001"
        assert q.name == "上证指数"
        assert q.price == 3250.60
        assert q.change_pct == 1.25
        assert q.change_amount == 40.10
        assert q.high == 3260.00
        assert q.low == 3240.00

    def test_default_values_are_none(self):
        q = StockQuote(code="sh000001")
        assert q.name is None
        assert q.price is None
        assert q.change_pct is None
        assert q.change_amount is None
        assert q.high is None
        assert q.low is None

    def test_is_valid_returns_true_when_price_present(self):
        q = StockQuote(code="sh000001", name="test", price=10.0)
        assert q.is_valid is True

    def test_is_valid_returns_false_when_price_none(self):
        q = StockQuote(code="sh000001")
        assert q.is_valid is False

    def test_direction_up(self):
        q = StockQuote(code="sh000001", change_pct=1.5)
        assert q.direction == "up"

    def test_direction_down(self):
        q = StockQuote(code="sh000001", change_pct=-0.5)
        assert q.direction == "down"

    def test_direction_flat(self):
        q = StockQuote(code="sh000001", change_pct=0.0)
        assert q.direction == "flat"

    def test_direction_flat_when_none(self):
        q = StockQuote(code="sh000001")
        assert q.direction == "flat"

    def test_format_change_pct_positive(self):
        q = StockQuote(code="sh000001", change_pct=2.35)
        assert q.fmt_change_pct == "+2.35%"

    def test_format_change_pct_negative(self):
        q = StockQuote(code="sh000001", change_pct=-1.50)
        assert q.fmt_change_pct == "-1.50%"

    def test_format_change_pct_zero(self):
        q = StockQuote(code="sh000001", change_pct=0.0)
        assert q.fmt_change_pct == "0.00%"

    def test_format_change_pct_none(self):
        q = StockQuote(code="sh000001")
        assert q.fmt_change_pct == "—"

    def test_equality_by_code(self):
        a = StockQuote(code="sh000001", price=10.0)
        b = StockQuote(code="sh000001", price=11.0)
        assert a == b  # same code = same stock

    def test_inequality_different_code(self):
        a = StockQuote(code="sh000001")
        b = StockQuote(code="sz000001")
        assert a != b

    def test_hashable(self):
        s = {StockQuote(code="sh000001"), StockQuote(code="sh000001"), StockQuote(code="sz000001")}
        assert len(s) == 2

    def test_repr(self):
        q = StockQuote(code="sh000001", name="上证指数", price=3250.60)
        r = repr(q)
        assert "sh000001" in r
        assert "上证指数" in r
        assert "3250.6" in r


class TestWatchlistItem:
    """A stock entry in the watchlist with code and optional alias."""

    def test_create_with_code_only(self):
        item = WatchlistItem(code="sh000001")
        assert item.code == "sh000001"
        assert item.name is None

    def test_create_with_name(self):
        item = WatchlistItem(code="hk00700", name="腾讯")
        assert item.code == "hk00700"
        assert item.name == "腾讯"

    def test_normalize_code_lowercase(self):
        item = WatchlistItem(code="SH000001")
        assert item.code == "sh000001"

    def test_validate_valid_code_no_raise(self):
        item = WatchlistItem(code="sh000001")
        item.validate()  # should not raise

    def test_validate_invalid_code_raises(self):
        item = WatchlistItem(code="invalid")
        with pytest.raises(ValueError, match="Invalid stock code"):
            item.validate()

    def test_serialize_to_config_entry(self):
        item = WatchlistItem(code="sh000001")
        assert item.to_config_entry() == "sh000001"

    def test_parse_from_config_string(self):
        item = WatchlistItem.from_config("hk00700")
        assert item.code == "hk00700"
        assert item.name is None

    def test_parse_from_config_with_spaces(self):
        item = WatchlistItem.from_config("  sh000001  ")
        assert item.code == "sh000001"


# ---------------------------------------------------------------------------
# AlertRule
# ---------------------------------------------------------------------------


class TestAlertRule:
    """Alert rule creation and checking."""

    def test_price_above_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_ABOVE, value=450.0)
        q = StockQuote(code="hk00700", price=451.0)
        assert rule.check(q) is True

    def test_price_above_not_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_ABOVE, value=450.0)
        q = StockQuote(code="hk00700", price=449.0)
        assert rule.check(q) is False

    def test_price_below_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_BELOW, value=400.0)
        q = StockQuote(code="hk00700", price=399.0)
        assert rule.check(q) is True

    def test_price_below_not_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_BELOW, value=400.0)
        q = StockQuote(code="hk00700", price=401.0)
        assert rule.check(q) is False

    def test_pct_above_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PCT_ABOVE, value=5.0)
        q = StockQuote(code="hk00700", change_pct=5.5)
        assert rule.check(q) is True

    def test_pct_above_not_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PCT_ABOVE, value=5.0)
        q = StockQuote(code="hk00700", change_pct=4.9)
        assert rule.check(q) is False

    def test_pct_below_fires(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PCT_BELOW, value=3.0)
        q = StockQuote(code="hk00700", change_pct=-3.5)
        assert rule.check(q) is True

    def test_pct_below_not_fires_positive(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PCT_BELOW, value=3.0)
        q = StockQuote(code="hk00700", change_pct=3.5)
        assert rule.check(q) is False

    def test_invalid_quote_does_not_fire(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_ABOVE, value=450.0)
        q = StockQuote(code="hk00700")  # no price
        assert rule.check(q) is False

    def test_describe_price(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_ABOVE, value=450.0)
        assert "价格上破" in rule.describe()
        assert "450.0" in rule.describe()

    def test_describe_pct(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PCT_ABOVE, value=5.0)
        assert "涨幅超" in rule.describe()
        assert "5.0%" in rule.describe()

    def test_to_config_dict(self):
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_ABOVE, value=450.0)
        d = rule.to_config_dict()
        assert d == {"code": "hk00700", "type": "price_above", "value": 450.0}

    def test_from_config_dict(self):
        rule = AlertRule.from_config_dict({"code": "hk00700", "type": "price_above", "value": 450.0})
        assert rule.code == "hk00700"
        assert rule.alert_type == AlertType.PRICE_ABOVE
        assert rule.value == 450.0
        assert rule.triggered is False

    def test_triggered_flag_prevents_repeat(self):
        """Once triggered, should not fire again until condition clears."""
        rule = AlertRule(code="hk00700", alert_type=AlertType.PRICE_ABOVE, value=450.0, triggered=True)
        q = StockQuote(code="hk00700", price=460.0)
        # check() still returns True (condition met), but caller should respect triggered flag
        assert rule.check(q) is True
        assert rule.triggered is True  # stays triggered
