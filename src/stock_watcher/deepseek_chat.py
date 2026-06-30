"""DeepSeek AI chat client with stock context injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from stock_watcher.config import DeepSeekConfig

if TYPE_CHECKING:
    from stock_watcher.models import Position, StockQuote

DEEPSEEK_TIMEOUT = 20  # LLM may be slow


_SYSTEM_PROMPT = """你是一个股票助手机器人，通过企业微信/飞书回复用户关于他们持仓的问题。

回复规则：
1. 使用下面的「实时数据」上下文回答问题
2. 数据精确到小数点后两位，涨跌幅用百分比，盈亏用人民币元
3. 简洁专业，用户问什么答什么，不要过度展开
4. 如果问的数据不在上下文中，如实说未监控
5. 统一用中文回答
"""


def _build_context(
    quotes: dict[str, dict],
    positions: dict[str, dict],
    hkd_rate: float,
) -> str:
    """Build a context block from current stock data for the LLM."""
    lines = ["## 实时持仓数据（港元已按汇率 %.4f 转为人民币）" % hkd_rate, ""]

    # Position stocks
    lines.append("### 持仓股")
    for code, p in positions.items():
        q = quotes.get(code, {})
        price = q.get("price", "—")
        name = q.get("name", "—")
        pct = q.get("change_pct", "—")
        if isinstance(pct, (int, float)):
            pct = f"{pct:+.2f}%"
        cost = p.get("cost", "—")
        qty = p.get("quantity", "—")
        pnl = p.get("pnl", "—")
        if isinstance(pnl, (int, float)):
            pnl = f"{pnl:+.2f}"
        mval = p.get("market_value", "—")
        if isinstance(mval, (int, float)):
            mval = f"{mval:,.2f}"

        lines.append(
            f"- {code} {name}：现价 {price}，涨跌 {pct}，"
            f"成本 {cost}，持仓 {qty} 股，市值 {mval}，盈亏 {pnl} 元"
        )

    # Watchlist-only stocks
    wl_only = [c for c in quotes if c not in positions]
    if wl_only:
        lines.append("")
        lines.append("### 自选盯盘")
        for code in wl_only:
            q = quotes[code]
            price = q.get("price", "—")
            name = q.get("name", "—")
            pct = q.get("change_pct", "—")
            if isinstance(pct, (int, float)):
                pct = f"{pct:+.2f}%"
            lines.append(f"- {code} {name}：现价 {price}，涨跌 {pct}")

    return "\n".join(lines)


def _is_hk(code: str) -> bool:
    return code.startswith("hk")


def _build_context_from_store(
    latest_quotes: dict[str, StockQuote],
    positions: dict[str, Position],
    hkd_rate: float,
) -> str:
    """Build context dict for DeepSeek from app state."""
    quotes_dict: dict[str, dict] = {}
    for code, q in latest_quotes.items():
        quotes_dict[code] = {
            "code": code,
            "name": q.name,
            "price": q.price,
            "change_pct": q.change_pct,
        }

    pos_dict: dict[str, dict] = {}
    from stock_watcher.models import Position

    for code, p in positions.items():
        if not p.is_valid:
            continue
        q = latest_quotes.get(code)
        rate = hkd_rate if _is_hk(code) else 1.0
        price = q.price if q and q.price else 0.0
        pos_dict[code] = {
            "cost": round(p.cost * rate, 4),
            "quantity": p.quantity,
            "available": p.available,
            "market_value": round(p.market_value(price) * rate, 2),
            "pnl": round(p.pnl(price) * rate, 2),
        }

    return _build_context(quotes_dict, pos_dict, hkd_rate)


async def ask_deepseek(
    cfg: DeepSeekConfig,
    context: str,
    user_question: str,
) -> str:
    """Send a question + context to DeepSeek, return the answer."""
    if not cfg.is_configured:
        return "请先配置 DeepSeek API Key (config.yaml → deepseek → api_key)"

    url = f"{cfg.api_base.rstrip('/')}/v1/chat/completions"

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "system", "content": context},
        {"role": "user", "content": user_question},
    ]

    try:
        async with httpx.AsyncClient(timeout=DEEPSEEK_TIMEOUT) as client:
            resp = await client.post(
                url,
                json={
                    "model": cfg.model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 800,
                },
                headers={
                    "Authorization": f"Bearer {cfg.api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        return f"DeepSeek API 返回错误 (HTTP {resp.status_code})"
    except Exception as exc:
        return f"调用 DeepSeek 失败：{exc}"
