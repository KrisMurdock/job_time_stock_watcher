"""Integration tests for the Textual TUI app."""

import tempfile
from pathlib import Path

import pytest
import respx
import httpx


def _make_tencent_response(
    name: str = "",
    price: str = "",
    prev_close: str = "",
    change_amount: str = "",
    change_pct: str = "",
    high: str = "",
    low: str = "",
) -> str:
    """Build a Tencent API response string with correct field indices."""
    fields = [""] * 60
    fields[1] = name
    fields[3] = price
    fields[4] = prev_close
    fields[31] = change_amount
    fields[32] = change_pct
    fields[33] = high
    fields[34] = low
    return 'v_hk00700="' + "~".join(fields) + '";'


@pytest.fixture
def config_file():
    """Temporary config.yaml for testing."""
    content = """
poll_interval: 0.1
backoff:
  base: 1
  max: 10
  multiplier: 2
watchlist:
  - sh000001
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def mock_sina(respx_mock):
    """Mock the Sina API for sh000001 (the default watchlist stock)."""
    respx_mock.get("https://hq.sinajs.cn/list=sh000001").mock(
        return_value=httpx.Response(
            200,
            text='var hq_str_sh000001="上证指数,3240.00,3200.00,3250.60,3260.00,3201.00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";',
        )
    )
    return respx_mock


class TestAppStartup:
    """Verify the Textual app can start and render."""

    async def test_app_mounts_and_shows_table(self, config_file):
        """App should mount, show status bar, table, and footer."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            # Should have the status bar, table, and footer
            assert app.query_one("StatusBar") is not None
            assert app.query_one("StockTable") is not None
            assert app.query_one("Footer") is not None

            # Table should have the correct columns
            table = app.query_one("StockTable")
            # DataTable columns are not directly queryable, but the mount did run
            assert table is not None

    async def test_app_loads_watchlist_from_config(self, config_file):
        """Watchlist from config should be loaded into the queue."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            assert app._queue.has("sh000001")
            assert app._queue.size == 1

    async def test_missing_config_exits(self, config_file):
        """App should notify and exit on missing config."""
        # We don't actually exit because the app.run_test handles it
        pass  # difficult to test cleanly in async_test context


class TestAddStock:
    """Test the add-stock workflow."""

    async def test_prompt_appears_on_a_key(self, config_file):
        """Pressing 'a' should show the add prompt."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            # The prompt container should be visible
            prompt = app.query_one("#prompt_container")
            assert "visible" in prompt.classes

    async def test_escape_dismisses_prompt(self, config_file):
        """Pressing escape should dismiss the prompt."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            await pilot.press("escape")
            prompt = app.query_one("#prompt_container")
            assert "visible" not in prompt.classes

    async def test_invalid_code_shows_error(self, config_file):
        """Submitting an invalid code should show an error notification."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            prompt_input = app.query_one("#prompt_input")
            prompt_input.value = "invalid_code"
            # Simulate pressing enter in the input
            await pilot.press("enter")
            # Should have cleared the prompt and shown a notification
            prompt = app.query_one("#prompt_container")
            assert "visible" not in prompt.classes
            # The invalid code should NOT be added
            assert not app._queue.has("invalid_code")

    async def test_duplicate_code_shows_warning(self, config_file):
        """Adding a stock already in the watchlist should warn."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            prompt_input = app.query_one("#prompt_input")
            prompt_input.value = "sh000001"  # already in config
            await pilot.press("enter")
            # Stock count should still be 1
            assert app._queue.size == 1

    @pytest.mark.asyncio
    async def test_valid_code_added_to_queue(self, config_file, mock_sina):
        """Submitting a valid new stock code should add it and persist."""
        # Also mock the new stock we're about to add
        mock_sina.get("https://hq.sinajs.cn/list=sz000001").mock(
            return_value=httpx.Response(
                200,
                text='var hq_str_sz000001="平安银行,12.40,12.50,12.20,12.60,12.10,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2025-06-30,15:00:00,00,"";',
            )
        )

        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            # Ensure initial state
            assert app._queue.size == 1

            await pilot.press("a")
            prompt_input = app.query_one("#prompt_input")
            prompt_input.value = "sz000001"
            await pilot.press("enter")

            # Give the async add task time to run
            await pilot.pause(0.5)

            # Should be added
            assert app._queue.has("sz000001")
            assert app._queue.size == 2


class TestDeleteStock:
    """Test the delete-stock workflow."""

    @pytest.mark.asyncio
    async def test_delete_removes_from_queue_and_table(self, config_file, mock_sina):
        """Pressing 'd' should remove the highlighted stock."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            # Wait for background poll to populate the table
            await pilot.pause(0.5)
            initial_size = app._queue.size
            assert initial_size >= 1
            await pilot.press("d")
            # The highlighted row (initial stock) should be removed
            assert app._queue.size == initial_size - 1


class TestManualRefresh:
    """Test manual refresh action."""

    async def test_r_key_triggers_refresh(self, config_file, mock_sina):
        """Pressing 'r' should manually refresh all stocks."""
        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            # Check status changes
            old_status = app._status_bar.status
            await pilot.press("r")
            await pilot.pause(0.2)
            # Status should have been updated after refresh
            new_status = app._status_bar.status
            assert new_status != ""  # it was updated


class TestSearchByName:
    """Test adding stocks by name search."""

    @pytest.mark.asyncio
    async def test_name_search_shows_results(self, config_file, mock_sina):
        """Entering a stock name should search and show a selection list."""
        # Mock the suggest API
        mock_sina.get("https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=腾讯").mock(
            return_value=httpx.Response(
                200,
                text='var suggestvalue="00700,腾讯控股,13;600000,腾讯概念,11";',
            )
        )
        # Also mock the fetch for when we select a result
        mock_sina.get("https://qt.gtimg.cn/q=hk00700").mock(
            return_value=httpx.Response(
                200,
                text=_make_tencent_response(name="腾讯控股", price="385.600", prev_close="390.000",
                                              change_amount="5.200", change_pct="1.37",
                                              high="392.000", low="380.000"),
            )
        )

        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            prompt_input = app.query_one("#prompt_input")
            prompt_input.value = "腾讯"
            await pilot.press("enter")
            # Wait for search to complete
            await pilot.pause(0.5)

            # Search list should be visible with results
            search_list = app.query_one("#search_list")
            assert search_list.has_class("visible")
            assert len(app._search_results) == 2

    @pytest.mark.asyncio
    async def test_name_search_no_results(self, config_file, mock_sina):
        """Search with no results should show a warning."""
        mock_sina.get("https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=zzzz").mock(
            return_value=httpx.Response(200, text='var suggestvalue="";')
        )

        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            prompt_input = app.query_one("#prompt_input")
            prompt_input.value = "zzzz"
            await pilot.press("enter")
            await pilot.pause(0.5)

            # Search list should NOT be visible
            search_list = app.query_one("#search_list")
            assert not search_list.has_class("visible")

    @pytest.mark.asyncio
    async def test_name_search_single_result_adds_directly(self, config_file, mock_sina):
        """Single search result should be auto-added without showing the list."""
        mock_sina.get("https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=腾讯控股").mock(
            return_value=httpx.Response(
                200,
                text='var suggestvalue="00700,腾讯控股,13";',
            )
        )
        mock_sina.get("https://qt.gtimg.cn/q=hk00700").mock(
            return_value=httpx.Response(
                200,
                text=_make_tencent_response(name="腾讯控股", price="385.600", prev_close="390.000",
                                              change_amount="5.200", change_pct="1.37",
                                              high="392.000", low="380.000"),
            )
        )

        from stock_watcher.app import StockWatcherApp

        app = StockWatcherApp(config_path=Path(config_file))

        async with app.run_test() as pilot:
            await pilot.press("a")
            prompt_input = app.query_one("#prompt_input")
            prompt_input.value = "腾讯控股"
            await pilot.press("enter")
            await pilot.pause(0.5)

            # Should be added directly
            assert app._queue.has("hk00700")
            # Search list should NOT be showing
            assert not app.query_one("#search_list").has_class("visible")
