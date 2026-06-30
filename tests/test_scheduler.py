"""Unit tests for stock_watcher.scheduler — polling queue, backoff, trading hours."""

import datetime as dt
import pytest

from stock_watcher.scheduler import (
    TradingCalendar,
    BackoffController,
    PollQueue,
    is_a_share_trading_time,
    is_hk_trading_time,
    is_us_trading_time,
    is_any_market_open,
    TRADING_SCHEDULES,
)


# ---------------------------------------------------------------------------
# Trading hours — pure functions
# ---------------------------------------------------------------------------
class TestIsAShareTradingTime:
    def test_monday_morning_session(self):
        """Monday 10:00 Beijing → trading."""
        t = dt.datetime(2025, 6, 30, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is True

    def test_monday_lunch_break(self):
        """Monday 12:00 Beijing → NOT trading."""
        t = dt.datetime(2025, 6, 30, 12, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is False

    def test_monday_afternoon_session(self):
        """Monday 14:00 Beijing → trading."""
        t = dt.datetime(2025, 6, 30, 14, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is True

    def test_saturday(self):
        """Saturday → NOT trading."""
        t = dt.datetime(2025, 6, 28, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is False

    def test_sunday(self):
        """Sunday → NOT trading."""
        t = dt.datetime(2025, 6, 29, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is False

    def test_before_open(self):
        """9:00 Beijing → NOT trading."""
        t = dt.datetime(2025, 6, 30, 9, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is False

    def test_after_close(self):
        """15:30 Beijing → NOT trading."""
        t = dt.datetime(2025, 6, 30, 15, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is False


class TestIsHKTradingTime:
    def test_monday_morning_session(self):
        """Monday 10:00 HKT → trading."""
        t = dt.datetime(2025, 6, 30, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_hk_trading_time(t) is True

    def test_monday_lunch_break(self):
        """Monday 12:30 HKT → NOT trading."""
        t = dt.datetime(2025, 6, 30, 12, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_hk_trading_time(t) is False

    def test_monday_afternoon_session(self):
        """Monday 14:00 HKT → trading."""
        t = dt.datetime(2025, 6, 30, 14, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_hk_trading_time(t) is True

    def test_closing_auction_16_05(self):
        """16:05 HKT → still trading (closing auction until 16:10)."""
        t = dt.datetime(2025, 6, 30, 16, 5, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_hk_trading_time(t) is True

    def test_after_close_16_30(self):
        """16:30 HKT → NOT trading."""
        t = dt.datetime(2025, 6, 30, 16, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_hk_trading_time(t) is False

    def test_saturday(self):
        t = dt.datetime(2025, 6, 28, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_hk_trading_time(t) is False


class TestIsUSTradingTime:
    def test_us_open_edt_monday_night(self):
        """EDT: 21:30-04:00. Monday 22:00 CST should be open."""
        t = dt.datetime(2025, 6, 30, 22, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_us_trading_time(t) is True

    def test_us_open_edt_tuesday_early(self):
        """EDT: 21:30-04:00. Tuesday 02:00 CST should still be open."""
        t = dt.datetime(2025, 7, 1, 2, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_us_trading_time(t) is True

    def test_us_closed_before_open_edt(self):
        """EDT: 21:30-04:00. 21:00 CST should be closed."""
        t = dt.datetime(2025, 6, 30, 21, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_us_trading_time(t) is False

    def test_us_closed_after_close_edt(self):
        """EDT: 21:30-04:00. 05:00 CST should be closed."""
        t = dt.datetime(2025, 7, 1, 5, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_us_trading_time(t) is False

    def test_us_closed_saturday(self):
        t = dt.datetime(2025, 6, 28, 22, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_us_trading_time(t) is False

    def test_us_open_est_winter(self):
        """EST: 22:30-05:00. December Monday 23:00 CST should be open."""
        t = dt.datetime(2025, 12, 15, 23, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_us_trading_time(t) is True


class TestIsAnyMarketOpen:
    def test_both_open_monday_morning(self):
        t = dt.datetime(2025, 6, 30, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_any_market_open(t) is True

    def test_none_open_saturday(self):
        t = dt.datetime(2025, 6, 28, 12, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_any_market_open(t) is False

    def test_hk_only_after_a_share_close(self):
        """15:30 Beijing: A-share closed, HK still open (closing auction until 16:10)."""
        t = dt.datetime(2025, 6, 30, 15, 30, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert is_a_share_trading_time(t) is False
        assert is_hk_trading_time(t) is True
        assert is_any_market_open(t) is True


# ---------------------------------------------------------------------------
# TradingCalendar
# ---------------------------------------------------------------------------
class TestTradingCalendar:
    def test_is_trading_for_sh_code(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 30, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert cal.is_trading("sh000001", t) is True
        assert cal.is_trading("sz000001", t) is True

    def test_is_trading_for_hk_code(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 30, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert cal.is_trading("hk00700", t) is True

    def test_is_trading_none_at_saturday(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 28, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert cal.is_trading("sh000001", t) is False
        assert cal.is_trading("hk00700", t) is False

    def test_is_trading_us_at_edt(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 30, 22, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert cal.is_trading("usaapl", t) is True

    def test_is_trading_us_closed_weekend(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 28, 22, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        assert cal.is_trading("usaapl", t) is False

    def test_status_string_open(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 30, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        status = cal.status_string(t)
        assert "交易中" in status

    def test_status_string_closed(self):
        cal = TradingCalendar()
        t = dt.datetime(2025, 6, 28, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        status = cal.status_string(t)
        assert "休市" in status


# ---------------------------------------------------------------------------
# BackoffController
# ---------------------------------------------------------------------------
class TestBackoffController:
    def test_initial_delay_is_base(self):
        bc = BackoffController(base=5, max_delay=120, multiplier=2)
        assert bc.current_delay == 5

    def test_backoff_doubles(self):
        bc = BackoffController(base=5, max_delay=120, multiplier=2)
        bc.backoff()
        assert bc.current_delay == 10
        bc.backoff()
        assert bc.current_delay == 20

    def test_backoff_caps_at_max(self):
        bc = BackoffController(base=60, max_delay=100, multiplier=2)
        bc.backoff()
        assert bc.current_delay == 100  # capped

    def test_reset_restores_base(self):
        bc = BackoffController(base=5, max_delay=120, multiplier=2)
        bc.backoff()
        bc.backoff()
        assert bc.current_delay == 20
        bc.reset()
        assert bc.current_delay == 5

    def test_consecutive_failures_count(self):
        bc = BackoffController(base=5, max_delay=120, multiplier=2)
        assert bc.consecutive_failures == 0
        bc.backoff()
        assert bc.consecutive_failures == 1
        bc.backoff()
        assert bc.consecutive_failures == 2
        bc.reset()
        assert bc.consecutive_failures == 0

    def test_is_backed_off(self):
        bc = BackoffController(base=5, max_delay=120, multiplier=2)
        assert bc.is_backed_off is False
        bc.backoff()
        assert bc.is_backed_off is True

    def test_jitter_is_applied(self):
        """The actual delay returned includes jitter — test the range."""
        bc = BackoffController(base=10, max_delay=120, multiplier=2)
        bc.backoff()
        # With jitter factor 0.25, delay should be in [15, 25]  (20 ± 5)
        delay = bc.get_delay()
        assert 15.0 <= delay <= 25.0

    def test_from_config_wires_values(self):
        from stock_watcher.config import BackoffConfig
        cfg = BackoffConfig(base=7, max_delay=90, multiplier=3)
        bc = BackoffController.from_config(cfg)
        assert bc._base == 7
        assert bc._max == 90
        assert bc._multiplier == 3


# ---------------------------------------------------------------------------
# PollQueue
# ---------------------------------------------------------------------------
class TestPollQueue:
    def test_next_cycles_through_stocks(self):
        pq = PollQueue(["sh000001", "sz000001", "hk00700"])
        codes = [pq.next(), pq.next(), pq.next(), pq.next()]
        assert codes == ["sh000001", "sz000001", "hk00700", "sh000001"]

    def test_single_stock(self):
        pq = PollQueue(["sh000001"])
        assert pq.next() == "sh000001"
        assert pq.next() == "sh000001"

    def test_empty_queue_returns_none(self):
        pq = PollQueue([])
        assert pq.next() is None

    def test_add_stock(self):
        pq = PollQueue(["sh000001"])
        pq.add("hk00700")
        # Should appear in next cycle
        codes = [pq.next(), pq.next()]
        assert "sh000001" in codes
        assert "hk00700" in codes

    def test_remove_stock(self):
        pq = PollQueue(["sh000001", "sz000001", "hk00700"])
        pq.remove("sz000001")
        # Two full cycles should never include sz000001
        codes = [pq.next() for _ in range(4)]
        assert "sz000001" not in codes
        assert "sh000001" in codes
        assert "hk00700" in codes

    def test_remove_last_stock_leaves_empty(self):
        pq = PollQueue(["sh000001"])
        pq.remove("sh000001")
        assert pq.next() is None

    def test_remove_nonexistent_is_noop(self):
        pq = PollQueue(["sh000001", "sz000001"])
        pq.remove("hk00700")  # not in list
        assert pq.next() == "sh000001"
        assert pq.next() == "sz000001"

    def test_add_duplicate_is_noop(self):
        pq = PollQueue(["sh000001"])
        pq.add("sh000001")
        codes = [pq.next() for _ in range(3)]
        assert codes.count("sh000001") == 3  # appears once per cycle, not twice

    def test_has_stock(self):
        pq = PollQueue(["sh000001", "hk00700"])
        assert pq.has("sh000001") is True
        assert pq.has("sz000001") is False

    def test_size(self):
        pq = PollQueue(["sh000001", "sz000001", "hk00700"])
        assert pq.size == 3
        pq.remove("sh000001")
        assert pq.size == 2

    def test_all_codes_returns_copy(self):
        original = ["sh000001", "hk00700"]
        pq = PollQueue(original)
        result = pq.all_codes
        assert result == original
        result.append("sz000001")
        assert pq.size == 2  # original not mutated
