"""塔科夫 WebSocket 的入站帧上限、令牌桶和带超时的发送。"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

CLOSE_TOO_LARGE = 1009
SEND_TIMEOUT_SEC = 5.0


class FrameTooLarge(Exception):
    """入站帧超过上限；调用方以 1009 关闭。"""


async def receive_json_bounded(ws: WebSocket, *, max_chars: int) -> Any:
    """读一帧 JSON；超过 max_chars 不解析直接拒绝。"""
    message = await ws.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000), message.get("reason"))
    text = message.get("text")
    if text is None:
        data = message.get("bytes") or b""
        if len(data) > max_chars:
            raise FrameTooLarge
        text = data.decode("utf-8")
    elif len(text) > max_chars:
        raise FrameTooLarge
    return json.loads(text)


async def send_json_timeout(
    ws: WebSocket, payload: Any, *, timeout: float = SEND_TIMEOUT_SEC
) -> bool:
    """发不出去或对端读得太慢都算失败，交给调用方摘掉这条连接。"""
    try:
        await asyncio.wait_for(ws.send_json(payload), timeout=timeout)
    except Exception:  # noqa: BLE001
        return False
    return True


async def close_quietly(ws: WebSocket, code: int, *, timeout: float = SEND_TIMEOUT_SEC) -> None:
    try:
        await asyncio.wait_for(ws.close(code=code), timeout=timeout)
    except Exception:  # noqa: BLE001
        pass


class TokenBucket:
    """单连接令牌桶：rate 个/秒回填，最多攒 capacity 个；拿不到就丢这一帧。"""

    __slots__ = ("_rate", "_capacity", "_tokens", "_stamp", "_clock")

    def __init__(
        self,
        rate: float,
        capacity: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate = float(rate)
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._clock = clock
        self._stamp = clock()

    def take(self, cost: float = 1.0) -> bool:
        now = self._clock()
        elapsed = max(0.0, now - self._stamp)
        self._stamp = now
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        if self._tokens < cost:
            return False
        self._tokens -= cost
        return True
