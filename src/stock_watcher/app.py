"""Textual TUI dashboard for real-time stock monitoring (A-share + HK)."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Input,
    Label,
    ListView,
    ListItem,
    Static,
)
from textual.binding import Binding

from stock_watcher.config import load_config, save_watchlist, save_alerts, RequestConfig
from stock_watcher.fetcher import get_fetcher, FetchError, search_stocks, SearchResult
from stock_watcher.models import StockQuote, Market, AlertRule, AlertType
from stock_watcher.scheduler import (
    PollQueue,
    BackoffController,
    TradingCalendar,
)


# ---------------------------------------------------------------------------
# Color constants (A-share convention: red = up, green = down)
# ---------------------------------------------------------------------------
UP_COLOR = "#ff4444"
DOWN_COLOR = "#00cc66"
FLAT_COLOR = "#aaaaaa"
UP_BG = "#3d1a1a"
DOWN_BG = "#1a3d24"

# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------


class StatusBar(Static):
    """Top bar showing market status, clock, stats, and latency."""

    status: reactive[str] = reactive("")
    last_update: reactive[str] = reactive("—")
    errors: reactive[int] = reactive(0)
    latency: reactive[str] = reactive("—")
    total: reactive[int] = reactive(0)
    up_count: reactive[int] = reactive(0)
    down_count: reactive[int] = reactive(0)
    flat_count: reactive[int] = reactive(0)

    def watch_status(self, _: str) -> None:
        self.refresh()

    def watch_last_update(self, _: str) -> None:
        self.refresh()

    def watch_errors(self, _: int) -> None:
        self.refresh()

    def watch_latency(self, _: str) -> None:
        self.refresh()

    def watch_total(self, _: int) -> None:
        self.refresh()

    def watch_up_count(self, _: int) -> None:
        self.refresh()

    def watch_down_count(self, _: int) -> None:
        self.refresh()

    def watch_flat_count(self, _: int) -> None:
        self.refresh()

    def render(self) -> str:
        now = dt.datetime.now().strftime("%H:%M:%S")
        parts = [f"[bold]📊 {self.status}[/bold]"]
        parts.append(f"🕐 {now}")
        parts.append(f"⏱ {self.latency}")
        parts.append(
            f"📈 [bold]监控 {self.total} 只[/bold]  "
            f"[{UP_COLOR}]↑{self.up_count}[/]  "
            f"[{DOWN_COLOR}]↓{self.down_count}[/]  "
            f"[{FLAT_COLOR}]→{self.flat_count}[/]"
        )
        if self.errors > 0:
            parts.append(f"[bold #ffaa00]⚠ 错误 {self.errors}[/]")
        return "  │  ".join(parts)


# ---------------------------------------------------------------------------
# Stock table
# ---------------------------------------------------------------------------


class StockTable(DataTable):
    """DataTable specialised for stock quote display."""

    def __init__(self) -> None:
        super().__init__(cursor_type="row", zebra_stripes=False)

    def on_mount(self) -> None:
        self.add_columns(
            " ",          # direction arrow
            "代码",
            "名称",
            "现价",
            "涨跌幅",
            "涨跌额",
            "最高",
            "最低",
        )
        # No default sort — rows appear in config order

    def update_quote(self, quote: StockQuote) -> None:
        """Insert or update a row for the given quote."""
        row_key = quote.code

        cells = [
            self._fmt_dir(quote.direction),
            f"[bold]{quote.code}[/bold]",
            quote.name or "—",
            self._fmt_price(quote.price),
            self._fmt_pct(quote.change_pct),
            self._fmt_amount(quote.change_amount),
            self._fmt_price(quote.high),
            self._fmt_price(quote.low),
        ]

        try:
            self.remove_row(row_key)
        except Exception:
            pass

        self.add_row(*cells, key=row_key)

    def get_row_count(self) -> int:
        return self.row_count

    def remove_row_by_key(self, key: str) -> None:
        try:
            self.remove_row(key)
        except Exception:
            pass

    def get_highlighted_key(self) -> Optional[str]:
        if self.row_count == 0:
            return None
        try:
            row = self.coordinate_to_cell_key(self.cursor_coordinate)
            return row.row_key.value if row else None
        except Exception:
            return None

    # -- formatters -------------------------------------------------------

    @staticmethod
    def _fmt_dir(direction: str) -> str:
        if direction == "up":
            return f"[bold {UP_COLOR}]↑[/]"
        elif direction == "down":
            return f"[bold {DOWN_COLOR}]↓[/]"
        return f"[{FLAT_COLOR}]→[/]"

    @staticmethod
    def _fmt_price(val: Optional[float]) -> str:
        if val is None:
            return "     —"
        return f"{val:>8.2f}"

    @staticmethod
    def _fmt_pct(val: Optional[float]) -> str:
        if val is None:
            return "       —"
        if val == 0:
            return "   0.00%"
        sign = "+" if val > 0 else ""
        color = UP_COLOR if val > 0 else DOWN_COLOR
        return f"[bold {color}]{sign}{val:>6.2f}%[/]"

    @staticmethod
    def _fmt_amount(val: Optional[float]) -> str:
        if val is None:
            return "       —"
        if val == 0:
            return "    0.00"
        sign = "+" if val > 0 else ""
        color = UP_COLOR if val > 0 else DOWN_COLOR
        return f"[{color}]{sign}{val:>7.2f}[/]"


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class StockWatcherApp(App):
    """Real-time stock price monitor for A-share and HK markets."""

    CSS = """
    Screen {
        background: #0d1117;
    }

    StatusBar {
        dock: top;
        height: 1;
        background: #161b22;
        color: #c9d1d9;
        padding: 0 1;
    }

    StockTable {
        height: 1fr;
        border: solid #30363d;
        background: #0d1117;
    }

    StockTable > .datatable--header {
        background: #161b22;
        color: #8b949e;
        text-style: bold;
    }

    StockTable > .datatable--cursor {
        background: #1f3a5f;
        color: #e6edf3;
    }

    Footer {
        background: #161b22;
        color: #8b949e;
    }

    Footer > .footer--key {
        background: #21262d;
        color: #e3b341;
        text-style: bold;
    }

    Footer > .footer--description {
        color: #c9d1d9;
    }

    #prompt_container {
        dock: bottom;
        height: 3;
        background: #161b22;
        padding: 0 1;
        border-top: solid #30363d;
        visibility: hidden;
    }

    #prompt_container.visible {
        visibility: visible;
    }

    #prompt_label {
        height: 1;
        color: #c9d1d9;
    }

    #prompt_input {
        height: 1;
        margin: 0 0 1 0;
    }

    #search_list {
        dock: bottom;
        height: auto;
        max-height: 12;
        background: #161b22;
        border: solid #58a6ff;
        visibility: hidden;
    }

    #search_list.visible {
        visibility: visible;
    }

    #search_list > .listview--item {
        color: #c9d1d9;
    }

    #search_list > .listview--item.highlight {
        background: #1f3a5f;
    }
    """

    BINDINGS = [
        Binding("a", "add_stock", "添加"),
        Binding("d", "delete_stock", "删除"),
        Binding("t", "set_alert", "告警"),
        Binding("r", "manual_refresh", "刷新"),
        Binding("q", "quit", "退出"),
        Binding("escape", "cancel_prompt", "取消", show=False),
    ]

    config_path: Path = Path("config.yaml")

    def __init__(self, config_path: Optional[Path] = None):
        super().__init__()
        if config_path:
            self.config_path = Path(config_path)

    def compose(self) -> ComposeResult:
        yield StatusBar()
        yield StockTable()
        yield Footer()
        yield Vertical(
            Label("输入股票代码或名称（如 sh000001 / 腾讯），回车确认：", id="prompt_label"),
            Input(id="prompt_input", placeholder="sh000001"),
            id="prompt_container",
        )
        yield ListView(id="search_list")

    def on_mount(self) -> None:
        try:
            self._cfg = load_config(self.config_path)
            self._config_mtime = os.path.getmtime(self.config_path)
        except FileNotFoundError:
            self.notify(f"配置文件未找到: {self.config_path}", severity="error")
            self.exit()
            return

        self._calendar = TradingCalendar()
        self._queue = PollQueue(list(self._cfg.watchlist))
        self._backoff = BackoffController.from_config(self._cfg.backoff)
        self._request_cfg = self._cfg.request
        self._poll_interval = self._cfg.poll_interval

        self._table: StockTable = self.query_one(StockTable)
        self._status_bar: StatusBar = self.query_one(StatusBar)
        self._prompt_container: Vertical = self.query_one("#prompt_container")
        self._prompt_input: Input = self.query_one("#prompt_input")
        self._prompt_label: Label = self.query_one("#prompt_label")
        self._search_list: ListView = self.query_one("#search_list")

        # Holds the latest quote for every stock (code → StockQuote)
        self._latest_quotes: dict[str, StockQuote] = {}

        # Alert rules loaded from config
        self._alerts: list[AlertRule] = list(self._cfg.alerts)

        self._prompt_mode: Optional[str] = None
        self._alert_target: Optional[str] = None  # stock code for alert setup
        self._search_results: list[SearchResult] = []
        self._stopped = False

        self._poll_loop()

    # ------------------------------------------------------------------
    # Key binding gate
    # ------------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self._prompt_mode is not None or self._search_list.has_class("visible"):
            if action in ("add_stock", "delete_stock", "set_alert", "manual_refresh", "quit"):
                return False
        return True

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    @work(exclusive=False)
    async def _poll_loop(self) -> None:
        while not self._stopped:
            # Check for config file changes
            self._reload_config_if_changed()

            code = self._queue.next()

            if code is None:
                await asyncio.sleep(1)
                continue

            if not self._calendar.is_trading(code):
                await asyncio.sleep(2)
                continue

            if self._backoff.is_backed_off:
                delay = self._backoff.get_delay()
                self._update_status()
                await asyncio.sleep(delay)

            await self._fetch_one(code)
            await asyncio.sleep(self._poll_interval)

    async def _fetch_one(self, code: str) -> None:
        t0 = time.monotonic()
        try:
            fetcher = get_fetcher(code, self._request_cfg)
            quote = await fetcher.fetch(code)
        except FetchError as e:
            if e.is_retryable:
                self._backoff.backoff()
            self._status_bar.errors = self._backoff.consecutive_failures
            self._update_status()
            return

        elapsed_ms = (time.monotonic() - t0) * 1000
        self._backoff.reset()
        self._status_bar.errors = 0
        self._status_bar.latency = f"{elapsed_ms:.0f}ms"

        if quote.is_valid:
            self._latest_quotes[code] = quote
            self._table.update_quote(quote)
            # Check alerts
            self._check_alerts(quote)
        else:
            cells = ["[#555555]→[/]", code, "—", "     —", "       —", "       —", "     —", "     —"]
            try:
                self._table.remove_row(code)
            except Exception:
                pass
            self._table.add_row(*cells, key=code)

        self._update_status()

    def _update_status(self) -> None:
        sb = self._status_bar
        sb.status = self._calendar.status_string()
        if self._backoff.is_backed_off:
            sb.status += f" 退避{self._backoff.current_delay:.0f}s"

        # Stats
        quotes = self._latest_quotes.values()
        sb.total = len(self._queue.all_codes)
        sb.up_count = sum(1 for q in quotes if q.direction == "up")
        sb.down_count = sum(1 for q in quotes if q.direction == "down")
        sb.flat_count = sb.total - sb.up_count - sb.down_count

    # ------------------------------------------------------------------
    # Config hot-reload
    # ------------------------------------------------------------------

    def _reload_config_if_changed(self) -> None:
        """Reload config.yaml if it was modified externally."""
        try:
            mtime = os.path.getmtime(self.config_path)
        except OSError:
            return

        if mtime <= self._config_mtime:
            return

        self._config_mtime = mtime

        try:
            new_cfg = load_config(self.config_path)
        except Exception:
            self.notify("配置文件变更但解析失败，保留当前配置", severity="warning")
            return

        # Sync watchlist: add new codes, remove deleted codes
        new_watchlist = set(new_cfg.watchlist)
        old_watchlist = set(self._queue.all_codes)

        added = new_watchlist - old_watchlist
        removed = old_watchlist - new_watchlist

        for code in sorted(removed):
            self._queue.remove(code)
            self._table.remove_row_by_key(code)
            self._latest_quotes.pop(code, None)
            self._alerts = [a for a in self._alerts if a.code != code]

        for code in sorted(added):
            if Market.is_valid_code(code):
                self._queue.add(code)
                asyncio.create_task(self._fetch_one(code))

        # Sync alerts
        self._alerts = list(new_cfg.alerts)

        # Sync poll interval and backoff
        self._poll_interval = new_cfg.poll_interval
        self._backoff = BackoffController.from_config(new_cfg.backoff)

        if added or removed:
            names = []
            if added:
                names.append(f"+{len(added)}只")
            if removed:
                names.append(f"-{len(removed)}只")
            self.notify(f"配置文件已更新（{'，'.join(names)}）")

        self._update_status()

    # ------------------------------------------------------------------
    # Manual refresh
    # ------------------------------------------------------------------

    @work(exclusive=False)
    async def action_manual_refresh(self) -> None:
        self._status_bar.status = "手动刷新..."
        for code in self._queue.all_codes:
            await self._fetch_one(code)
            await asyncio.sleep(1)
        self._update_status()

    # ------------------------------------------------------------------
    # Add stock
    # ------------------------------------------------------------------

    def action_add_stock(self) -> None:
        if self._search_list.has_class("visible"):
            self._hide_search_list()
            return

        self._prompt_mode = "add"
        self._prompt_container.add_class("visible")
        self._prompt_input.value = ""
        self._prompt_input.focus()

    async def _on_add_submit(self, raw: str) -> None:
        text = raw.strip().lower()
        if not text:
            return
        if self._search_list.has_class("visible"):
            return

        if Market.is_valid_code(text):
            self._add_stock_by_code(text)
            self.action_cancel_prompt()
            return

        await self._search_and_show(text)

    def _add_stock_by_code(self, code: str) -> None:
        if self._queue.has(code):
            self.notify(f"已在监控列表中: {code}", severity="warning")
            return

        self._queue.add(code)
        save_watchlist(self.config_path, self._queue.all_codes)
        asyncio.create_task(self._fetch_one(code))
        self.notify(f"已添加: {code}")
        self._update_status()

    async def _search_and_show(self, query: str) -> None:
        self._prompt_container.remove_class("visible")

        results = await search_stocks(query, self._request_cfg)

        if not results:
            self.notify(f"未找到与 '{query}' 相关的股票", severity="warning")
            self.action_cancel_prompt()
            return

        if len(results) == 1:
            r = results[0]
            self.notify(f"找到: {r.name} ({r.code})，正在添加...")
            self._add_stock_by_code(r.code)
            self.action_cancel_prompt()
            return

        self._search_results = results
        self._search_list.clear()
        for r in results:
            self._search_list.append(
                ListItem(Label(f"  {r.code}  │  {r.name}  │  {r.market.upper()}"))
            )
        self._search_list.add_class("visible")
        self._search_list.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not self._search_list.has_class("visible"):
            return

        idx = self._search_list.index
        if idx is not None and 0 <= idx < len(self._search_results):
            self._add_stock_by_code(self._search_results[idx].code)

        self._hide_search_list()
        self.action_cancel_prompt()

    def _hide_search_list(self) -> None:
        self._search_list.remove_class("visible")
        self._search_list.clear()
        self._search_results = []

    # ------------------------------------------------------------------
    # Delete stock
    # ------------------------------------------------------------------

    def action_delete_stock(self) -> None:
        key = self._table.get_highlighted_key()
        if key is None:
            self.notify("没有选中的股票", severity="warning")
            return

        self._table.remove_row_by_key(key)
        self._queue.remove(key)
        self._latest_quotes.pop(key, None)
        # Also remove alerts for this stock
        self._alerts = [a for a in self._alerts if a.code != key]
        save_watchlist(self.config_path, self._queue.all_codes)
        save_alerts(self.config_path, self._alerts)
        self.notify(f"已删除: {key}")
        self._update_status()

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def action_set_alert(self) -> None:
        """Set a price or change-% alert for the highlighted stock."""
        key = self._table.get_highlighted_key()
        if key is None:
            self.notify("没有选中的股票", severity="warning")
            return

        self._prompt_mode = "alert"
        self._alert_target = key
        self._prompt_container.add_class("visible")
        self._prompt_input.value = ""
        self._prompt_label.update(
            f"为 [bold]{key}[/bold] 设置告警。格式: [bold]类型 数值[/bold]"
            f"  类型: [bold]pa[/bold]=价格上破 [bold]pb[/bold]=价格下破 [bold]ca[/bold]=涨幅超 [bold]cb[/bold]=跌幅超"
            f"  例: [bold]pa 450[/bold] 表示价格突破450时告警"
        )
        self._prompt_input.focus()

    def _check_alerts(self, quote: StockQuote) -> None:
        """Check all alert rules against a new quote and fire if triggered."""
        for alert in self._alerts:
            if alert.code != quote.code:
                continue

            if alert.triggered:
                # Check if condition has cleared (for re-arm)
                if not alert.check(quote):
                    alert.triggered = False
                continue

            if alert.check(quote):
                alert.triggered = True
                self._fire_alert(alert, quote)

    def _fire_alert(self, alert: AlertRule, quote: StockQuote) -> None:
        """Fire an alert: TUI notification + system notification."""
        msg = f"🚨 {quote.name or alert.code} {alert.describe()}！现价 {quote.price:.2f}"
        self.notify(msg, severity="warning", timeout=10)

        # System notification (non-blocking)
        try:
            subprocess.run(
                ["notify-send", "📈 Stock Watcher 告警", msg],
                timeout=2,
                capture_output=True,
            )
        except Exception:
            pass  # notify-send not available — that's fine

    async def _on_alert_submit(self, raw: str) -> None:
        """Parse alert specification from user input."""
        parts = raw.strip().lower().split()
        if len(parts) < 2:
            self.notify("格式错误。例: pa 450 或 ca 5", severity="error")
            return

        type_map = {
            "pa": AlertType.PRICE_ABOVE,
            "pb": AlertType.PRICE_BELOW,
            "ca": AlertType.PCT_ABOVE,
            "cb": AlertType.PCT_BELOW,
        }

        alert_type = type_map.get(parts[0])
        if alert_type is None:
            self.notify(f"未知告警类型: {parts[0]}。可用: pa/pb/ca/cb", severity="error")
            return

        try:
            value = float(parts[1])
        except ValueError:
            self.notify(f"数值无效: {parts[1]}", severity="error")
            return

        code = self._alert_target
        # Remove any existing alert of same type for same stock
        self._alerts = [a for a in self._alerts if not (a.code == code and a.alert_type == alert_type)]
        self._alerts.append(AlertRule(code=code, alert_type=alert_type, value=value))
        save_alerts(self.config_path, self._alerts)

        desc = self._alerts[-1].describe()
        self.notify(f"已为 {code} 设置告警: {desc}")

    # ------------------------------------------------------------------
    # Prompt handling
    # ------------------------------------------------------------------

    def action_cancel_prompt(self) -> None:
        self._prompt_mode = None
        self._alert_target = None
        self._prompt_container.remove_class("visible")
        self._hide_search_list()
        # Restore default prompt label
        self._prompt_label.update(
            "输入股票代码或名称（如 sh000001 / 腾讯），回车确认："
        )
        self.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._prompt_mode == "add":
            asyncio.create_task(self._on_add_submit(event.value))
        elif self._prompt_mode == "alert":
            asyncio.create_task(self._on_alert_submit(event.value))
            self.action_cancel_prompt()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(config_path: Optional[str] = None) -> None:
    path = Path(config_path) if config_path else Path("config.yaml")
    if not path.is_absolute():
        path = Path.cwd() / path
    app = StockWatcherApp(config_path=path)
    app.run()


if __name__ == "__main__":
    import sys
    config_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_arg)
