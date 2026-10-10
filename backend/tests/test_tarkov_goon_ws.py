"""Goon tracker WebSocket: origin check, off-loop auth, frame cap, stalled-client drop."""

from __future__ import annotations

import asyncio
import functools

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from app.api.guides import tarkov_goons as goons_api
from app.services.tarkov import goon_tracker_hub as goon_hub_mod
from app.services.tarkov import goon_tracker_ws as goon_ws_svc
from app.services.tarkov import ws_limits
from app.services.tarkov.goon_tracker_hub import GoonTrackerHub


class _FakeSocket:
    def __init__(self, *, stall: bool = False) -> None:
        self.sent: list[dict] = []
        self.closed: int | None = None
        self.stall = stall

    async def send_json(self, payload: dict) -> None:
        if self.stall:
            await asyncio.sleep(3600)
        self.sent.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.closed = code


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(goons_api.router)
    return TestClient(app)


def test_goons_ws_rejects_cross_site_origin(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(goon_ws_svc, "_load_user", lambda token: calls.append(token))
    with _client().websocket_connect(
        "/goons/ws", headers={"origin": "https://evil.example"}
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as caught:
            ws.receive_json()
    assert caught.value.code == 4403
    assert calls == []


def test_goons_ws_loads_user_off_the_event_loop(monkeypatch) -> None:
    on_loop: list[bool] = []

    def load_user(token: str) -> None:
        try:
            asyncio.get_running_loop()
            on_loop.append(True)
        except RuntimeError:
            on_loop.append(False)
        raise PermissionError("unauth")

    monkeypatch.setattr(goon_ws_svc, "_load_user", load_user)
    with _client().websocket_connect("/goons/ws") as ws:
        ws.send_json({"event": "auth", "token": "t"})
        with pytest.raises(WebSocketDisconnect) as caught:
            ws.receive_json()
    assert caught.value.code == goon_ws_svc.CLOSE_UNAUTHORIZED
    assert on_loop == [False]


def test_goons_ws_closes_oversized_frame() -> None:
    with _client().websocket_connect("/goons/ws") as ws:
        ws.send_text("x" * (goon_ws_svc.MAX_FRAME_CHARS + 1))
        with pytest.raises(WebSocketDisconnect) as caught:
            ws.receive_json()
    assert caught.value.code == ws_limits.CLOSE_TOO_LARGE


def test_goon_hub_drops_stalled_client_without_blocking_others(monkeypatch) -> None:
    monkeypatch.setattr(
        goon_hub_mod,
        "send_json_timeout",
        functools.partial(ws_limits.send_json_timeout, timeout=0.05),
    )
    hub = GoonTrackerHub()
    fast = _FakeSocket()
    slow = _FakeSocket(stall=True)

    async def run() -> None:
        await hub.join(fast)  # type: ignore[arg-type]
        await hub.join(slow)  # type: ignore[arg-type]
        await asyncio.to_thread(hub.publish, {"event": "goons"})
        for _ in range(20):
            await asyncio.sleep(0)
            pending = list(hub._tasks)
            if pending:
                await asyncio.wait_for(asyncio.gather(*pending), timeout=2)
        assert fast.sent == [{"event": "goons"}]
        assert slow.closed == goon_hub_mod.CLOSE_SLOW_CONSUMER
        assert hub._clients == {fast}

    asyncio.run(run())
