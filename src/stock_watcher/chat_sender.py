"""Feishu (Lark) custom bot webhook notification sender."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import time

import httpx

from stock_watcher.config import ChatConfig
from stock_watcher.models import StockQuote


FEISHU_WEBHOOK_TIMEOUT = 10  # seconds


def _generate_sign(timestamp_seconds: int, secret: str) -> str:
    """Generate HMAC-SHA256 signature for Feishu webhook verification."""
    msg = f"{timestamp_seconds}\n{secret}"
    h = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256)
    return h.hexdigest()  # Feishu uses hex, NOT base64


def _build_card_header(title: str, color: str = "red") -> dict:
    return {
        "title": {"tag": "plain_text", "content": title},
        "template": color,
    }


def _build_card_md_row(label: str, value: str) -> dict:
    return {
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**{label}**：{value}"},
    }


def _color_pct(pct: float | None) -> str:
    """Return color-tagged change percent string for lark_md."""
    if pct is None:
        return "—"
    color = "red" if pct >= 0 else "green"
    return f"<font color='{color}'>{pct:+.2f}%</font>"


def _color_price(price: float | None, pct: float | None) -> str:
    """Return price string coloured by direction."""
    if price is None:
        return "—"
    if pct is None:
        return f"{price:.2f}"
    color = "red" if pct >= 0 else "green"
    return f"<font color='{color}'>**{price:.2f}**</font>"


def _column_set(fields: list[tuple[str, str]]) -> dict:
    """Build a Feishu column_set element from (label, value) pairs."""
    columns = []
    for label, value in fields:
        columns.append({
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**{label}**\n{value}"}},
            ],
        })
    return {"tag": "column_set", "flex_mode": "bisect", "columns": columns}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_alert_card(
    code: str,
    name: str,
    rule_desc: str,
    price: float,
    change_pct: float | None = None,
) -> dict:
    """Build a Feishu interactive card for an alert notification."""
    now_str = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    pct_str = _color_pct(change_pct)
    price_str = _color_price(price, change_pct)

    elements = [
        _column_set([
            ("📌 代码", code),
            ("💰 现价", price_str),
        ]),
        _column_set([
            ("📛 名称", name),
            ("📈 涨跌幅", pct_str),
        ]),
        _column_set([
            ("🎯 触发条件", rule_desc),
            ("🕐 时间", now_str),
        ]),
    ]

    return {
        "msg_type": "interactive",
        "card": {
            "header": _build_card_header("🚨 股票告警触发", "red"),
            "elements": elements,
        },
    }


def build_summary_card(
    quotes: dict[str, StockQuote],
    positions: dict[str, "Position"] | None = None,
) -> dict:
    """Build a Feishu interactive card for daily summary with positions."""
    from stock_watcher.models import Position

    positions = positions or {}
    has_positions = any(p.is_valid for p in positions.values())
    now_str = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M"
    )

    # Build row lines in monospace-friendly format
    if has_positions:
        header_line = "代码      名称      现价      涨跌幅      持仓     可用     成本      市值"
        sep_line    = "────  ────  ──────  ──────  ────  ────  ──────  ────────"
    else:
        header_line = "代码      名称      现价      涨跌幅"
        sep_line    = "────  ────  ──────  ──────"

    lines = [header_line, sep_line]

    total_mval = 0.0

    for code, q in sorted(quotes.items()):
        pct_str = _color_pct(q.change_pct)
        price = f"{q.price:>6.2f}" if q.price is not None else "     —"
        name = (q.name or "—").ljust(4)[:4]

        row = f"{code:10s} {name:4s} {price}  {pct_str}"

        if has_positions:
            pos = positions.get(code)
            if pos and pos.is_valid and q.price:
                qty = f"{pos.quantity:>4d}"
                avail = f"{pos.available:>4d}"
                cost = f"{pos.cost:>6.2f}"
                mval = pos.market_value(q.price)
                mval_str = f"{mval:>8.0f}"
                total_mval += mval
                row += f"  {qty}  {avail}  {cost}  {mval_str}"
            else:
                row += "     —      —       —         —"

        lines.append(row)

    # Stats block
    if has_positions and total_mval > 0:
        lines.append("")
        lines.append(f"📊 **持仓总市值：{total_mval:,.0f} 元**")

    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines) or "暂无数据"},
        },
        {"tag": "hr"},
        _build_card_md_row("更新时间", now_str),
    ]

    return {
        "msg_type": "interactive",
        "card": {
            "header": _build_card_header(
                f"📊 每日持仓汇总 — {now_str[:10]}", "blue"
            ),
            "elements": elements,
        },
    }


async def send_feishu_card(cfg: ChatConfig, card: dict) -> bool:
    """Send a card message to a Feishu webhook.  Returns True on success."""
    if not cfg.is_configured:
        return False

    payload: dict = {"msg_type": card["msg_type"], "card": card["card"]}
    ts = int(time.time())
    if cfg.feishu_secret:
        payload["timestamp"] = str(ts)
        payload["sign"] = _generate_sign(ts, cfg.feishu_secret)

    try:
        async with httpx.AsyncClient(timeout=FEISHU_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(
                cfg.feishu_webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        # Feishu returns {"StatusCode": 0, "StatusMessage": "success"}
        if resp.status_code == 200:
            body = resp.json()
            return body.get("StatusCode") == 0 or body.get("code") == 0
        return False
    except Exception:
        return False
