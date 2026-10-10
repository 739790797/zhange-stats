"""Tarkov WebSocket limits: frame cap, token bucket, timed sends."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import WebSocketDisconnect

from app.services.tarkov.ws_limits import (
    FrameTooLarge,
    TokenBucket,
    receive_json_bounded,
    send_json_timeout,
)


class _Inbox:
    def __init__(self, *messages: dict) -> None:
        self._messages = list(messages)

    async def receive(self) -> dict:
        return self._messages.pop(0)


class _Stalled:
    async def send_json(self, payload: object) -> None:
        await asyncio.sleep(3600)


def test_token_bucket_refills_at_rate_up_to_capacity() -> None:
    now = [0.0]
    bucket = TokenBucket(2, 3, clock=lambda: now[0])
    assert [bucket.take() for _ in range(4)] == [True, True, True, False]
    now[0] += 0.5
    assert bucket.take() is True
    assert bucket.take() is False
    now[0] += 60
    assert [bucket.take() for _ in range(4)] == [True, True, True, False]


def test_receive_json_bounded_rejects_oversized_text_and_bytes() -> None:
    async def run() -> None:
        ok = _Inbox({"type": "websocket.receive", "text": '{"event": "ping"}'})
        assert await receive_json_bounded(ok, max_chars=64) == {"event": "ping"}  # type: ignore[arg-type]
        big_text = _Inbox({"type": "websocket.receive", "text": "x" * 65})
        with pytest.raises(FrameTooLarge):
            await receive_json_bounded(big_text, max_chars=64)  # type: ignore[arg-type]
        big_bytes = _Inbox({"type": "websocket.receive", "bytes": b"x" * 65})
        with pytest.raises(FrameTooLarge):
            await receive_json_bounded(big_bytes, max_chars=64)  # type: ignore[arg-type]
        small_bytes = _Inbox({"type": "websocket.receive", "bytes": b'{"a": 1}'})
        assert await receive_json_bounded(small_bytes, max_chars=64) == {"a": 1}  # type: ignore[arg-type]
        gone = _Inbox({"type": "websocket.disconnect", "code": 1001})
        with pytest.raises(WebSocketDisconnect) as caught:
            await receive_json_bounded(gone, max_chars=64)  # type: ignore[arg-type]
        assert caught.value.code == 1001

    asyncio.run(run())


def test_send_json_timeout_reports_stalled_peer() -> None:
    async def run() -> bool:
        return await send_json_timeout(_Stalled(), {"event": "x"}, timeout=0.05)  # type: ignore[arg-type]

    assert asyncio.run(asyncio.wait_for(run(), timeout=2)) is False
