"""Feishu bot WebSocket event listener + DeepSeek AI reply.

Connects to Feishu via WebSocket long connection (app_access_token),
receives @mention events, gathers current stock context, sends to DeepSeek,
and replies in-thread via the IM API (tenant_access_token).
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import TYPE_CHECKING

import httpx
import websockets  # type: ignore[import-untyped]
from websockets.exceptions import ConnectionClosed  # type: ignore[import-untyped]

from stock_watcher.config import ChatConfig, DeepSeekConfig

if TYPE_CHECKING:
    from stock_watcher.models import Position, StockQuote

FEISHU_API = "https://open.feishu.cn/open-apis"

# ---------------------------------------------------------------------------
# Access tokens
# ---------------------------------------------------------------------------


async def _get_token(endpoint: str, app_id: str, app_secret: str) -> str | None:
    """Generic Feishu internal token fetcher."""
    url = f"{FEISHU_API}/auth/v3/{endpoint}/internal"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "app_id": app_id,
                "app_secret": app_secret,
            })
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return data.get("app_access_token") or data.get("tenant_access_token")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# WebSocket event loop
# ---------------------------------------------------------------------------


async def run_bot_server(
    chat_cfg: ChatConfig,
    deepseek_cfg: DeepSeekConfig,
    get_quotes: callable,
    get_positions: callable,
    get_hkd_rate: callable,
    notify: callable,
    stop_event: asyncio.Event,
) -> None:
    """Main loop: connect WebSocket (app token), receive @mentions, reply (tenant token)."""
    if not chat_cfg.can_receive:
        notify("[bot] 缺少 feishu_app_id / feishu_app_secret，跳过 WebSocket")
        return

    ws_url = "wss://open.feishu.cn/open-apis/event/v1/ws/"

    while not stop_event.is_set():
        app_token = await _get_token("app_access_token", chat_cfg.feishu_app_id, chat_cfg.feishu_app_secret)
        if not app_token:
            notify("[bot] 获取 app_access_token 失败，10s 重试")
            await asyncio.sleep(10)
            continue

        tenant_token = await _get_token("tenant_access_token", chat_cfg.feishu_app_id, chat_cfg.feishu_app_secret)
        # tenant token can be re-fetched later if needed

        full_url = f"{ws_url}?token={app_token}"
        notify("[bot] WebSocket 已连接")

        try:
            async with websockets.connect(full_url, ping_interval=30, ping_timeout=10) as ws:
                while not stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except asyncio.TimeoutError:
                        continue

                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    asyncio.create_task(
                        _handle_event(
                            event, deepseek_cfg,
                            get_quotes, get_positions, get_hkd_rate, notify,
                        )
                    )
        except ConnectionClosed:
            notify("[bot] WebSocket 断开，5s 重连")
        except Exception as exc:
            notify(f"[bot] WebSocket 异常: {exc}")

        await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------


async def _handle_event(
    event: dict,
    deepseek_cfg: DeepSeekConfig,
    get_quotes: callable,
    get_positions: callable,
    get_hkd_rate: callable,
    notify: callable,
) -> None:
    """Parse one WebSocket event frame and reply if it's an @mention."""
    header = event.get("header", {})
    event_type = header.get("event_type", "")

    if event_type != "im.message.receive_v1":
        return

    ev = event.get("event", {})
    msg = ev.get("message", {})
    if msg.get("message_type") != "text":
        return

    text = msg.get("content", "")
    try:
        inner = json.loads(text)
        text = inner.get("text", text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Only respond to @mentions
    if "机器人" not in text and "@" not in text:
        return

    message_id = msg.get("message_id", "")
    if not message_id:
        return

    notify(f"[bot] 收到提问：{text[:80]}")

    # Gather context
    quotes = get_quotes()
    positions = get_positions()
    hkd_rate = get_hkd_rate()

    from stock_watcher.deepseek_chat import _build_context_from_store, ask_deepseek

    context = _build_context_from_store(quotes, positions, hkd_rate)
    answer = await ask_deepseek(deepseek_cfg, context, text)

    # Reply using tenant_access_token
    reply_success = await _reply_message(message_id, answer)
    if reply_success:
        notify(f"[bot] ✓ 已回复 ({len(answer)}字)")
    else:
        notify("[bot] ✗ 回复失败")


# ---------------------------------------------------------------------------
# Reply via IM API
# ---------------------------------------------------------------------------


async def _reply_message(message_id: str, content: str) -> bool:
    """Reply to a message in Feishu IM (uses environment token from main thread)."""
    # We re-fetch tenant token each time since it's cheap
    from stock_watcher.config import load_config
    from pathlib import Path

    try:
        cfg = load_config(Path("config.yaml"))
        if not cfg.chat or not cfg.chat.can_receive:
            return False
        tenant_token = await _get_token(
            "tenant_access_token", cfg.chat.feishu_app_id, cfg.chat.feishu_app_secret
        )
        if not tenant_token:
            return False

        url = f"{FEISHU_API}/im/v1/messages/{urllib.parse.quote(message_id)}/reply"
        body = {"content": json.dumps({"text": content}), "msg_type": "text"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url, json=body,
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
        return resp.status_code == 200 and resp.json().get("code") == 0
    except Exception:
        return False
