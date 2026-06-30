"""Core data models for stock_watcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Market(Enum):
    """Stock market identifier."""

    SHANGHAI = "sh"
    SHENZHEN = "sz"
    HONGKONG = "hk"

    @classmethod
    def from_code(cls, code: str) -> "Market":
        """Extract market from a prefixed stock code like 'sh000001'."""
        if not code or len(code) < 2:
            raise ValueError(f"code must have a 2-char prefix: {code!r}")
        prefix = code[:2].lower()
        try:
            return cls(prefix)
        except ValueError:
            raise ValueError(f"Unknown market prefix '{prefix}' in code {code!r}")

    @classmethod
    def is_valid_code(cls, code: str) -> bool:
        """Return True if the code has a known market prefix."""
        try:
            cls.from_code(code)
            return True
        except ValueError:
            return False


@dataclass(frozen=True)
class StockQuote:
    """Immutable snapshot of a stock price at a point in time.

    Equality is based on `code` only — two quotes for the same stock
    are considered equal regardless of price differences.
    """

    code: str = field(compare=True)
    name: Optional[str] = field(default=None, compare=False)
    price: Optional[float] = field(default=None, compare=False)
    change_pct: Optional[float] = field(default=None, compare=False)
    change_amount: Optional[float] = field(default=None, compare=False)
    high: Optional[float] = field(default=None, compare=False)
    low: Optional[float] = field(default=None, compare=False)

    @property
    def is_valid(self) -> bool:
        """A quote is valid only when price is available."""
        return self.price is not None

    @property
    def direction(self) -> str:
        """One of 'up', 'down', 'flat'."""
        if self.change_pct is None:
            return "flat"
        if self.change_pct > 0:
            return "up"
        if self.change_pct < 0:
            return "down"
        return "flat"

    @property
    def fmt_change_pct(self) -> str:
        """Formatted change percentage string, e.g. '+1.25%' or '—'."""
        if self.change_pct is None:
            return "—"
        sign = "+" if self.change_pct > 0 else ""
        return f"{sign}{self.change_pct:.2f}%"


@dataclass
class WatchlistItem:
    """A stock entry in the user's watchlist."""

    code: str
    name: Optional[str] = None

    def __post_init__(self) -> None:
        self.code = self.code.strip().lower()

    def validate(self) -> None:
        """Raise ValueError if the stock code is invalid."""
        if not Market.is_valid_code(self.code):
            raise ValueError(f"Invalid stock code: {self.code!r}")

    def to_config_entry(self) -> str:
        """Serialize to a single config string (the code)."""
        return self.code

    @classmethod
    def from_config(cls, raw: str) -> "WatchlistItem":
        """Deserialize from a config string."""
        return cls(code=raw.strip())
