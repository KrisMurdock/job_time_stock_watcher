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


def _color_pnl(pnl: float) -> str:
    """Return P&L string coloured red/green."""
    color = "red" if pnl >= 0 else "green"
    return f"<font color='{color}'>{pnl:+.0f}</font>"


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
    """Build a Feishu interactive card with two sections: 持仓信息 + 自选盯盘."""
    from stock_watcher.models import Position

    positions = positions or {}
    now_str = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M"
    )

    # Split into holdings and watchlist-only
    pos_codes = [c for c in sorted(quotes)
                 if (p := positions.get(c)) and p.is_valid]
    wl_codes = [c for c in sorted(quotes) if c not in pos_codes]

    elements: list[dict] = []
    total_mval = 0.0

    # Section 1: 持仓信息
    if pos_codes:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "📦 **持仓信息**"}})
        hdr = "代码      名称    现价      涨跌幅     持仓   可用    成本      市值      盈亏"
        sep = "────  ────  ──────  ──────  ────  ────  ───────  ────────  ────────"
        lines = [hdr, sep]

        for code in pos_codes:
            q = quotes[code]
            p = positions[code]
            pct = _color_pct(q.change_pct)
            price = f"{q.price:>6.2f}" if q.price is not None else "     —"
            name = (q.name or "—")[:4].ljust(4)

            qty = f"{p.quantity:>4d}"
            av  = f"{p.available:>4d}"
            cst = f"{p.cost:>7.3f}"

            if q.price:
                mval = p.market_value(q.price)
                mv = f"{mval:>8.0f}"
                pnl_val = p.pnl(q.price)
                pnl_s = _color_pnl(pnl_val)
                total_mval += mval
            else:
                mv = "       —"
                pnl_s = "       —"

            lines.append(f"{code:10s} {name:4s} {price}  {pct}  {qty}  {av}  {cst}  {mv}  {pnl_s}")

        lines.append(f"💰 **持仓总市值：{total_mval:,.0f} 元**")
        lines.append(f"📈 **持仓总盈亏：{_color_pnl(sum(positions[c].pnl(quotes[c].price or 0) for c in pos_codes))}**")
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})

    # Section 2: 自选盯盘
    if wl_codes:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "👀 **自选盯盘**"}})
        lines2 = ["代码      名称    现价      涨跌幅", "────  ────  ──────  ──────"]

        for code in wl_codes:
            q = quotes[code]
            pct = _color_pct(q.change_pct)
            price = f"{q.price:>6.2f}" if q.price is not None else "     —"
            name = (q.name or "—")[:4].ljust(4)
            lines2.append(f"{code:10s} {name:4s} {price}  {pct}")

        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines2)}})

    elements.append({"tag": "hr"})
    elements.append(_build_card_md_row("更新时间", now_str))

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
