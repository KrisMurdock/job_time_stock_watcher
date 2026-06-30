"""Unit tests for stock_watcher.config."""

import tempfile
from pathlib import Path

import pytest

from stock_watcher.config import (
    AppConfig,
    BackoffConfig,
    RequestConfig,
    load_config,
    save_watchlist,
    WATCHLIST_KEY,
)


# ---------------------------------------------------------------------------
# BackoffConfig
# ---------------------------------------------------------------------------
class TestBackoffConfig:
    def test_defaults(self):
        b = BackoffConfig()
        assert b.base == 5
        assert b.max == 120
        assert b.multiplier == 2

    def test_from_dict(self):
        b = BackoffConfig.from_dict({"base": 10, "max": 60, "multiplier": 3})
        assert b.base == 10
        assert b.max == 60
        assert b.multiplier == 3

    def test_from_dict_partial_fills_defaults(self):
        b = BackoffConfig.from_dict({"base": 8})
        assert b.base == 8
        assert b.max == 120
        assert b.multiplier == 2

    def test_from_empty_dict_uses_defaults(self):
        b = BackoffConfig.from_dict({})
        assert b.base == 5
        assert b.max == 120


# ---------------------------------------------------------------------------
# RequestConfig
# ---------------------------------------------------------------------------
class TestRequestConfig:
    def test_defaults(self):
        r = RequestConfig()
        assert r.timeout == 10
        assert len(r.user_agent_pool) > 0

    def test_from_dict_custom_agents(self):
        r = RequestConfig.from_dict({
            "timeout": 15,
            "user_agent_pool": ["Agent-A", "Agent-B"],
        })
        assert r.timeout == 15
        assert r.user_agent_pool == ["Agent-A", "Agent-B"]

    def test_get_random_ua_returns_from_pool(self):
        r = RequestConfig(user_agent_pool=["UA-1", "UA-2", "UA-3"])
        ua = r.get_random_ua()
        assert ua in ["UA-1", "UA-2", "UA-3"]

    def test_get_random_ua_single_entry(self):
        r = RequestConfig(user_agent_pool=["OnlyOne"])
        assert r.get_random_ua() == "OnlyOne"


# ---------------------------------------------------------------------------
# AppConfig
# ---------------------------------------------------------------------------
class TestAppConfig:
    def test_default_config(self):
        cfg = AppConfig()
        assert cfg.poll_interval == 2.5
        assert isinstance(cfg.backoff, BackoffConfig)
        assert isinstance(cfg.request, RequestConfig)
        assert cfg.watchlist == []
        assert cfg.proxies == []

    def test_from_dict_full(self):
        d = {
            "poll_interval": 3.0,
            "backoff": {"base": 7, "max": 90, "multiplier": 2},
            "request": {"timeout": 12, "user_agent_pool": ["UA"]},
            "watchlist": ["sh000001", "hk00700"],
            "proxies": ["http://proxy:8080"],
        }
        cfg = AppConfig.from_dict(d)
        assert cfg.poll_interval == 3.0
        assert cfg.backoff.base == 7
        assert cfg.request.timeout == 12
        assert cfg.watchlist == ["sh000001", "hk00700"]
        assert cfg.proxies == ["http://proxy:8080"]


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------
class TestLoadConfig:
    def test_load_valid_yaml(self):
        yaml_content = """
poll_interval: 3.0
backoff:
  base: 8
watchlist:
  - sh000001
  - hk00700
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            path = f.name

        try:
            cfg = load_config(Path(path))
            assert cfg.poll_interval == 3.0
            assert cfg.backoff.base == 8
            assert cfg.watchlist == ["sh000001", "hk00700"]
        finally:
            Path(path).unlink()

    def test_load_empty_yaml_returns_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            path = f.name

        try:
            cfg = load_config(Path(path))
            assert cfg.poll_interval == 2.5
        finally:
            Path(path).unlink()

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))


# ---------------------------------------------------------------------------
# save_watchlist
# ---------------------------------------------------------------------------
class TestSaveWatchlist:
    def test_save_and_reload(self):
        yaml_content = """
poll_interval: 2.5
backoff:
  base: 5
watchlist:
  - sh000001
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            path = f.name

        try:
            save_watchlist(Path(path), ["sh000001", "hk00700"])
            cfg = load_config(Path(path))
            assert cfg.watchlist == ["sh000001", "hk00700"]
        finally:
            Path(path).unlink()

    def test_save_creates_file_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "new_config.yaml"
            save_watchlist(cfg_path, ["hk00700"])
            loaded = load_config(cfg_path)
            assert loaded.watchlist == ["hk00700"]

    def test_save_preserves_other_settings(self):
        yaml_content = """
poll_interval: 4.0
backoff:
  base: 10
watchlist:
  - sh000001
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            path = f.name

        try:
            save_watchlist(Path(path), ["hk00700"])
            cfg = load_config(Path(path))
            assert cfg.poll_interval == 4.0
            assert cfg.backoff.base == 10
        finally:
            Path(path).unlink()
