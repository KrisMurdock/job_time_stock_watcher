"""Configuration loading, persistence, and watchlist management."""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# The YAML key for the watchlist
WATCHLIST_KEY = "watchlist"


# ---------------------------------------------------------------------------
# Config value objects
# ---------------------------------------------------------------------------


@dataclass
class BackoffConfig:
    """Exponential-backoff parameters for failed requests."""

    base: float = 5.0
    max: float = 120.0
    multiplier: float = 2.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BackoffConfig":
        return cls(
            base=float(d.get("base", 5)),
            max=float(d.get("max", 120)),
            multiplier=float(d.get("multiplier", 2)),
        )


@dataclass
class RequestConfig:
    """HTTP request configuration."""

    timeout: float = 10.0
    user_agent_pool: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ])

    def get_random_ua(self) -> str:
        """Return a random User-Agent from the pool."""
        return random.choice(self.user_agent_pool)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RequestConfig":
        timeout = float(d.get("timeout", 10))
        ua_pool = d.get("user_agent_pool", None)
        if ua_pool and isinstance(ua_pool, list) and len(ua_pool) > 0:
            return cls(timeout=timeout, user_agent_pool=[str(x) for x in ua_pool])
        return cls(timeout=timeout)


@dataclass
class AppConfig:
    """Top-level application configuration."""

    poll_interval: float = 2.5
    backoff: BackoffConfig = field(default_factory=BackoffConfig)
    request: RequestConfig = field(default_factory=RequestConfig)
    watchlist: list[str] = field(default_factory=list)
    proxies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AppConfig":
        return cls(
            poll_interval=float(d.get("poll_interval", 2.5)),
            backoff=BackoffConfig.from_dict(d.get("backoff", {})),
            request=RequestConfig.from_dict(d.get("request", {})),
            watchlist=[str(x) for x in d.get("watchlist", [])],
            proxies=[str(x) for x in d.get("proxies", [])],
        )


# ---------------------------------------------------------------------------
# I/O functions
# ---------------------------------------------------------------------------


def load_config(path: Path) -> AppConfig:
    """Load configuration from a YAML file.

    Raises FileNotFoundError if the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return AppConfig.from_dict(raw)


def save_watchlist(path: Path, watchlist: list[str]) -> None:
    """Persist only the watchlist section of the config, preserving everything else."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    else:
        raw = {}

    raw[WATCHLIST_KEY] = list(watchlist)

    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(raw, fh, default_flow_style=False, allow_unicode=True)
