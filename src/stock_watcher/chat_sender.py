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
    pct_str = f"{change_pct:+.2f}%" if change_pct is not None else "—"

    elements = [
        _build_card_md_row("代码", code),
        _build_card_md_row("名称", name),
        _build_card_md_row("现价", f"{price:.2f}"),
        _build_card_md_row("触发条件", rule_desc),
        {"tag": "hr"},
        _build_card_md_row("涨跌幅", pct_str),
        _build_card_md_row("时间", now_str),
    ]

    return {
        "msg_type": "interactive",
        "card": {
            "header": _build_card_header("⚠️ 股票告警", "red"),
            "elements": elements,
        },
    }


def build_summary_card(quotes: dict[str, StockQuote]) -> dict:
    """Build a Feishu interactive card for daily summary."""
    now_str = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime(
        "%Y-%m-%d %H:%M"
    )
    lines: list[str] = []
    for code, q in sorted(quotes.items()):
        pct = f"{q.change_pct:+.2f}%" if q.change_pct is not None else "—"
        price = f"{q.price:.2f}" if q.price is not None else "—"
        name = q.name or "—"
        lines.append(f"{code}  {name}  **{price}**  {pct}")

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
