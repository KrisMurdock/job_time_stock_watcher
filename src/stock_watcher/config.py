"""Configuration loading, persistence, and watchlist management."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from stock_watcher.models import AlertRule, Position


# The YAML key for the watchlist
WATCHLIST_KEY = "watchlist"
ALERTS_KEY = "alerts"


# ---------------------------------------------------------------------------
# Config value objects
# ---------------------------------------------------------------------------


@dataclass
class BackoffConfig:
    """Exponential-backoff parameters for failed requests."""

    base: float = 5.0
    max_delay: float = 120.0
    multiplier: float = 2.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BackoffConfig":
        return cls(
            base=float(d.get("base", 5)),
            max_delay=float(d.get("max", d.get("max_delay", 120))),
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


# ---------------------------------------------------------------------------
# EmailConfig
# ---------------------------------------------------------------------------


@dataclass
class EmailConfig:
    """SMTP email notification configuration (163 / QQ / Gmail etc.)."""

    smtp_host: str = "smtp.163.com"
    smtp_port: int = 587
    username: str = ""        # full email address
    password: str = ""        # SMTP auth code (NOT login password)
    from_addr: str = ""
    to_addr: str = ""         # recipient(s), comma-separated

    @property
    def is_configured(self) -> bool:
        """Return True if minimum required fields are filled."""
        return bool(self.smtp_host and self.username and self.password and self.to_addr)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EmailConfig":
        return cls(
            smtp_host=str(d.get("smtp_host", "smtp.163.com")),
            smtp_port=int(d.get("smtp_port", 587)),
            username=str(d.get("username", "")),
            password=str(d.get("password", "")),
            from_addr=str(d.get("from", "")),
            to_addr=str(d.get("to", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "username": self.username,
            "password": self.password,
            "from": self.from_addr,
            "to": self.to_addr,
        }


@dataclass
class AppConfig:
    """Top-level application configuration."""

    poll_interval: float = 2.5
    backoff: BackoffConfig = field(default_factory=BackoffConfig)
    request: RequestConfig = field(default_factory=RequestConfig)
    watchlist: list[str] = field(default_factory=list)
    alerts: list[AlertRule] = field(default_factory=list)
    proxies: list[str] = field(default_factory=list)
    positions: dict[str, Position] = field(default_factory=dict)
    alert_sound_command: str = ""
    email: Optional[EmailConfig] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AppConfig":
        pos_raw = d.get("positions", {}) or {}
        email_raw = d.get("email")
        return cls(
            poll_interval=float(d.get("poll_interval", 2.5)),
            backoff=BackoffConfig.from_dict(d.get("backoff", {})),
            request=RequestConfig.from_dict(d.get("request", {})),
            watchlist=[str(x) for x in d.get("watchlist", [])],
            alerts=[AlertRule.from_config_dict(a) for a in d.get("alerts") or []],
            proxies=[str(x) for x in d.get("proxies", [])],
            positions={k: Position.from_config(v) for k, v in pos_raw.items()},
            alert_sound_command=str(d.get("alert_sound_command", "")),
            email=EmailConfig.from_dict(email_raw) if email_raw else None,
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


def _save_yaml_list(path: Path, key: str, item_texts: list[str]) -> None:
    """Replace a top-level YAML list key in-place, preserving all comments.

    Reads the file as text, finds the ``key:`` block (from the key line
    through its indented list items), and replaces just that block.
    If *item_texts* is empty, writes ``key: []`` on one line.
    Each entry in *item_texts* is one complete list item — use newlines
    within an entry to produce multi-line dict items.
    """
    if item_texts:
        items_block = "\n".join(f"- {t}" for t in item_texts)
        new_block = f"{key}:\n{items_block}\n"
    else:
        new_block = f"{key}: []\n"

    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = ""

    # Match a top-level YAML key (no leading whitespace) followed by its
    # content — list items (starting with "-") and their continuation
    # lines (indented).  Stops before the next top-level key, comment, or
    # an empty line.
    pattern = re.compile(
        rf"^{re.escape(key)}:.*(?:\n(?:[ \t]+\S.*|-.*))*",
        re.MULTILINE,
    )

    if pattern.search(text):
        text = pattern.sub(new_block, text)
    else:
        # Key does not exist yet: append at end, with a blank separating
        # line when the file doesn't already end with one.
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n" + new_block

    path.write_text(text, encoding="utf-8")


def save_watchlist(path: Path, watchlist: list[str]) -> None:
    """Persist the watchlist, keeping all comments and other settings intact."""
    _save_yaml_list(path, WATCHLIST_KEY, list(watchlist))


def save_alerts(path: Path, alerts: list[AlertRule]) -> None:
    """Persist the alerts, keeping all comments and other settings intact."""
    items: list[str] = []
    for rule in alerts:
        d = rule.to_config_dict()
        items.append(f"code: {d['code']}\n  type: {d['type']}\n  value: {d['value']}")
    _save_yaml_list(path, ALERTS_KEY, items)


def save_positions(path: Path, positions: dict[str, "Position"]) -> None:
    """Persist positions to config.yaml, preserving comments."""
    key = "positions"
    if not positions:
        new_block = f"{key}: {{}}\n"
    else:
        lines = [f"{key}:"]
        for code, pos in positions.items():
            lines.append(f"  {code}:")
            lines.append(f"    cost: {pos.cost}")
            lines.append(f"    quantity: {pos.quantity}")
        new_block = "\n".join(lines) + "\n"

    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = ""

    pattern = re.compile(
        rf"^{re.escape(key)}:.*(?:\n(?:[ \t]+\S.*))*",
        re.MULTILINE,
    )

    if pattern.search(text):
        text = pattern.sub(new_block, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n" + new_block

    path.write_text(text, encoding="utf-8")
