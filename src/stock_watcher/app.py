"""Textual TUI dashboard for real-time stock monitoring (A-share + HK)."""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)
from textual.binding import Binding

from stock_watcher.config import load_config, save_watchlist, RequestConfig
from stock_watcher.fetcher import get_fetcher, FetchError
from stock_watcher.models import StockQuote, Market
from stock_watcher.scheduler import (
    PollQueue,
    BackoffController,
    TradingCalendar,
)


# ---------------------------------------------------------------------------
# Color constants (A-share convention: red = up, green = down)
# ---------------------------------------------------------------------------
UP_COLOR = "#ff4444"       # red
DOWN_COLOR = "#00cc66"     # green
FLAT_COLOR = "#cccccc"     # grey
HEADER_BG = "#1a1a2e"
BODY_BG = "#16213e"

# ---------------------------------------------------------------------------
# TUI Widgets
# ---------------------------------------------------------------------------


class StatusBar(Static):
    """Top bar showing market status, last update time, and error count."""

    status: reactive[str] = reactive("")
    last_update: reactive[str] = reactive("—")
    errors: reactive[int] = reactive(0)

    def watch_status(self, value: str) -> None:
        self.refresh()

    def watch_last_update(self, value: str) -> None:
        self.refresh()

    def watch_errors(self, value: int) -> None:
        self.refresh()

    def render(self) -> str:
        parts = [f"  📊 {self.status}  "]
        parts.append(f"  🕐 更新: {self.last_update}  ")
        if self.errors > 0:
            parts.append(f"  ⚠ 错误: {self.errors}  ")
        return "│".join(parts)


class StockTable(DataTable):
    """DataTable specialised for stock quote display."""

    def __init__(self) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        self.add_columns(
            "代码", "名称", "现价", "涨跌幅", "涨跌额", "最高", "最低",
        )

    def update_quote(self, quote: StockQuote) -> None:
        """Insert or update a row for the given quote."""
        row_key = quote.code

        # Format the cells
        cells = [
            quote.code,
            quote.name or "—",
            self._fmt_price(quote.price),
            self._fmt_pct(quote.change_pct),
            self._fmt_amount(quote.change_amount),
            self._fmt_price(quote.high),
            self._fmt_price(quote.low),
        ]

        # Remove old row if exists
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
        """Return the row_key of the currently highlighted row."""
        if self.row_count == 0:
            return None
        try:
            row = self.coordinate_to_cell_key(self.cursor_coordinate)
            return row.row_key.value if row else None
        except Exception:
            return None

    @staticmethod
    def _fmt_price(val: Optional[float]) -> str:
        if val is None:
            return "—"
        return f"{val:.2f}"

    @staticmethod
    def _fmt_pct(val: Optional[float]) -> str:
        if val is None:
            return "—"
        sign = "+" if val > 0 else ""
        return f"[{UP_COLOR if val > 0 else DOWN_COLOR if val < 0 else ''}]{sign}{val:.2f}%[/]"

    @staticmethod
    def _fmt_amount(val: Optional[float]) -> str:
        if val is None:
            return "—"
        sign = "+" if val > 0 else ""
        return f"[{UP_COLOR if val > 0 else DOWN_COLOR if val < 0 else ''}]{sign}{val:.2f}[/]"


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------


class StockWatcherApp(App):
    """Real-time stock price monitor for A-share and HK markets."""

    CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $panel;
        color: $text;
    }

    StockTable {
        height: 1fr;
        border: solid $accent;
    }

    #prompt_container {
        dock: bottom;
        height: 3;
        background: $panel;
        padding: 0 1;
        display: none;
    }

    #prompt_container.visible {
        display: block;
    }

    #prompt_label {
        height: 1;
        color: $text;
    }

    #prompt_input {
        height: 1;
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("a", "add_stock", "添加股票"),
        Binding("d", "delete_stock", "删除股票"),
        Binding("r", "manual_refresh", "手动刷新"),
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
            Label("输入股票代码（如 sh000001 / hk00700），回车确认：", id="prompt_label"),
            Input(id="prompt_input", placeholder="sh000001"),
            id="prompt_container",
        )

    def on_mount(self) -> None:
        """Load config and start the polling engine."""
        # Load configuration
        try:
            self._cfg = load_config(self.config_path)
        except FileNotFoundError:
            self.notify(f"配置文件未找到: {self.config_path}", severity="error")
            self.exit()
            return

        # Wire up components
        self._calendar = TradingCalendar()
        self._queue = PollQueue(list(self._cfg.watchlist))
        self._backoff = BackoffController.from_config(self._cfg.backoff)
        self._request_cfg = self._cfg.request
        self._poll_interval = self._cfg.poll_interval

        # Table reference
        self._table: StockTable = self.query_one(StockTable)
        self._status_bar: StatusBar = self.query_one(StatusBar)
        self._prompt_container: Vertical = self.query_one("#prompt_container")
        self._prompt_input: Input = self.query_one("#prompt_input")

        # State
        self._prompt_mode: Optional[str] = None  # "add" or None
        self._stopped = False

        # Kick off polling
        self._poll_loop()

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    @work(exclusive=False)
    async def _poll_loop(self) -> None:
        """Background worker: cycles through the queue, fetches one stock at a time."""
        while not self._stopped:
            code = self._queue.next()

            if code is None:
                # Empty queue
                await asyncio.sleep(1)
                continue

            # Skip if market is closed (unless manually forced — handled by flag)
            if not self._calendar.is_trading(code):
                await asyncio.sleep(2)
                continue

            # If backed off, wait before next request
            if self._backoff.is_backed_off:
                delay = self._backoff.get_delay()
                self._update_status()
                await asyncio.sleep(delay)

            # Fetch
            await self._fetch_one(code)
            await asyncio.sleep(self._poll_interval)

    async def _fetch_one(self, code: str) -> None:
        """Fetch a single stock quote and update the table."""
        try:
            fetcher = get_fetcher(code, self._request_cfg)
            quote = await fetcher.fetch(code)
        except FetchError as e:
            if e.is_retryable:
                self._backoff.backoff()
            self._status_bar.errors = self._backoff.consecutive_failures
            self._update_status()
            return

        # Success — reset backoff
        self._backoff.reset()
        self._status_bar.errors = 0

        # Update table
        if quote.is_valid:
            self._table.update_quote(quote)
        else:
            # Show placeholder row for stocks with no data yet
            cells = [code, "—", "—", "—", "—", "—", "—"]
            try:
                self._table.remove_row(code)
            except Exception:
                pass
            self._table.add_row(*cells, key=code)

        # Update status
        self._status_bar.last_update = dt.datetime.now().strftime("%H:%M:%S")
        self._update_status()

    def _update_status(self) -> None:
        """Refresh the status bar."""
        self._status_bar.status = self._calendar.status_string()
        if self._backoff.is_backed_off:
            self._status_bar.status += f" [退避 {self._backoff.current_delay:.0f}s]"

    # ------------------------------------------------------------------
    # Manual refresh
    # ------------------------------------------------------------------

    @work(exclusive=False)
    async def action_manual_refresh(self) -> None:
        """Force-refresh all stocks regardless of trading hours."""
        self._status_bar.status = "🔄 手动刷新..."
        codes = self._queue.all_codes
        for code in codes:
            await self._fetch_one(code)
            await asyncio.sleep(1)  # be gentle to the API
        self._update_status()

    # ------------------------------------------------------------------
    # Add stock
    # ------------------------------------------------------------------

    def action_add_stock(self) -> None:
        """Open the add-stock prompt."""
        self._prompt_mode = "add"
        self._prompt_container.add_class("visible")
        self._prompt_input.value = ""
        self._prompt_input.focus()

    async def _on_add_submit(self, raw: str) -> None:
        """Process add-stock submission."""
        code = raw.strip().lower()

        # Validate
        if not Market.is_valid_code(code):
            self.notify(f"无效的股票代码: {code}\n格式: sh000001 / sz000001 / hk00700", severity="error")
            return

        if self._queue.has(code):
            self.notify(f"已在监控列表中: {code}", severity="warning")
            return

        # Add to queue
        self._queue.add(code)

        # Persist
        save_watchlist(self.config_path, self._queue.all_codes)

        # Kick off an immediate fetch for the new stock
        await self._fetch_one(code)

        self.notify(f"已添加: {code}")
        self._update_status()

    # ------------------------------------------------------------------
    # Delete stock
    # ------------------------------------------------------------------

    def action_delete_stock(self) -> None:
        """Delete the currently highlighted stock."""
        key = self._table.get_highlighted_key()
        if key is None:
            self.notify("没有选中的股票", severity="warning")
            return

        self._table.remove_row_by_key(key)
        self._queue.remove(key)
        save_watchlist(self.config_path, self._queue.all_codes)
        self.notify(f"已删除: {key}")
        self._update_status()

    # ------------------------------------------------------------------
    # Prompt handling
    # ------------------------------------------------------------------

    def action_cancel_prompt(self) -> None:
        """Dismiss the add-stock prompt."""
        self._prompt_mode = None
        self._prompt_container.remove_class("visible")
        self.set_focus(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle prompt input submission."""
        if self._prompt_mode == "add":
            asyncio.create_task(self._on_add_submit(event.value))
        self.action_cancel_prompt()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(config_path: Optional[str] = None) -> None:
    """Launch the stock watcher TUI."""
    path = Path(config_path) if config_path else Path("config.yaml")
    if not path.is_absolute():
        # Resolve relative to CWD
        path = Path.cwd() / path
    app = StockWatcherApp(config_path=path)
    app.run()


if __name__ == "__main__":
    import sys
    config_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_arg)
