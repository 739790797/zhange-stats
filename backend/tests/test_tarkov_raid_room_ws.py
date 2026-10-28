"""Raid room WebSocket endpoint: origin check, frame cap, per-event rate limits, eviction."""

from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from time import monotonic

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from app.api.guides import tarkov_raid_rooms as rooms_api
from app.models.user import User, UserRole
from app.services.tarkov import raid_room_ws as room_ws_svc
from app.services.tarkov.raid_room_hub import CLOSE_EVICTED, CLOSE_TOO_MANY_SOCKETS, RoomSocketLimit, hub
from app.services.tarkov.ws_limits import CLOSE_TOO_LARGE, TokenBucket


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(rooms_api.router)
    return TestClient(app)


def _frozen() -> float:
    return 0.0


def _receive_frames_with_timeout(ws, count: int, timeout: float = 5.0) -> list[dict]:
    frames: Queue[tuple[bool, object]] = Queue()

    def receive() -> None:
        for _ in range(count):
            try:
                frames.put((True, ws.receive_json()))
            except BaseException as exc:
                frames.put((False, exc))
                return

    receiver = Thread(target=receive, daemon=True)
    receiver.start()
    deadline = monotonic() + timeout
    received: list[dict] = []
    for _ in range(count):
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            succeeded, value = frames.get(timeout=remaining)
        except Empty:
            break
        if not succeeded:
            raise value
        received.append(value)
    if len(received) != count:
        ws.close()
        receiver.join(timeout=1)
        raise AssertionError(f"Timed out waiting for {count} WebSocket frame(s)")
    return received


def test_ws_closes_extra_sockets_with_4429(monkeypatch) -> None:
    """每条连接一套令牌桶：同一账号在一间房里开第 4 条连接直接 4429 关掉。"""
    user = User(id=5, username="u5", display_name="五", password_hash="x", role=UserRole.user)
    monkeypatch.setattr(room_ws_svc, "_load_user", lambda token: user)
    monkeypatch.setattr(
        room_ws_svc,
        "_snapshot",
        lambda public_id, viewer: {"public_id": public_id, "is_member": True},
    )
    monkeypatch.setattr(room_ws_svc, "_touch_ws_member", lambda public_id, viewer: None)
    monkeypatch.setattr(room_ws_svc, "_is_member", lambda public_id, viewer: True)

    async def refuse(public_id, ws, user_id, client=""):
        raise RoomSocketLimit("user")

    monkeypatch.setattr(hub, "join", refuse)
    pid = "wscap0001"
    try:
        with _client().websocket_connect(f"/raid-rooms/{pid}/ws") as ws:
            ws.send_json({"event": "auth", "token": "t", "client": "web"})
            with pytest.raises(WebSocketDisconnect) as caught:
                _receive_frames_with_timeout(ws, 1)
        assert caught.value.code == CLOSE_TOO_MANY_SOCKETS
    finally:
        hub.close_room(pid)


def test_publish_key_owns_skips_when_database_missing() -> None:
    room_ws_svc._publish_key_owns("missing-room")


def test_ws_rejects_cross_site_origin_before_auth(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(room_ws_svc, "_load_user", lambda token: calls.append(token))
    with _client().websocket_connect("/raid-rooms/wsorigin1/ws", headers={"origin": "https://evil.example"}) as ws:
        with pytest.raises(WebSocketDisconnect) as caught:
            _receive_frames_with_timeout(ws, 1)
    assert caught.value.code == 4403
    assert calls == []


def test_ws_closes_oversized_first_frame(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(room_ws_svc, "_load_user", lambda token: calls.append(token))
    with _client().websocket_connect("/raid-rooms/wsbig0001/ws") as ws:
        ws.send_text("x" * (room_ws_svc.MAX_FRAME_CHARS + 1))
        with pytest.raises(WebSocketDisconnect) as caught:
            _receive_frames_with_timeout(ws, 1)
    assert caught.value.code == CLOSE_TOO_LARGE
    assert calls == []


def test_ws_drops_drafts_over_budget_and_evict_closes_socket(monkeypatch) -> None:
    user = User(id=5, username="u5", display_name="五", password_hash="x", role=UserRole.user)
    monkeypatch.setattr(room_ws_svc, "_load_user", lambda token: user)
    monkeypatch.setattr(
        room_ws_svc,
        "_snapshot",
        lambda public_id, viewer: {"public_id": public_id, "is_member": True},
    )
    monkeypatch.setattr(room_ws_svc, "_touch_ws_member", lambda public_id, viewer: None)
    monkeypatch.setattr(room_ws_svc, "_is_member", lambda public_id, viewer: True)
    monkeypatch.setattr(
        room_ws_svc,
        "_event_buckets",
        lambda: {
            "ping": TokenBucket(1, 100, clock=_frozen),
            "view_map": TokenBucket(1, 10, clock=_frozen),
            "draw_draft": TokenBucket(1, 3, clock=_frozen),
            "player_fix": TokenBucket(1, 5, clock=_frozen),
            "log_phase": TokenBucket(1, 10, clock=_frozen),
        },
    )
    published: list[dict] = []
    real_publish = hub.publish

    def record(public_id: str, payload: dict) -> None:
        published.append(payload)
        real_publish(public_id, payload)

    monkeypatch.setattr(hub, "publish", record)
    pid = "wsrate001"
    try:
        with _client().websocket_connect(f"/raid-rooms/{pid}/ws") as ws:
            ws.send_json({"event": "auth", "token": "t", "client": "web"})
            assert _receive_frames_with_timeout(ws, 1)[0]["event"] == "snapshot"
            ws.send_json({"event": "view_map", "map_id": "customs"})
            for _ in range(10):
                ws.send_json({"event": "draw_draft", "floor": "", "points": [[1, 2], [3, 4]]})
            ws.send_json({"event": "ping"})
            events = [row["event"] for row in _receive_frames_with_timeout(ws, 6)]
            assert sorted(events) == sorted(["presence", "view_map", "draw_draft", "draw_draft", "draw_draft", "pong"])
            assert sum(1 for row in published if row.get("event") == "draw_draft") == 3

            hub.evict(pid, user.id)
            assert _receive_frames_with_timeout(ws, 1) == [{"event": "member_leave", "user_id": 5}]
            with pytest.raises(WebSocketDisconnect) as caught:
                _receive_frames_with_timeout(ws, 1)
            assert caught.value.code == CLOSE_EVICTED
            assert hub.online_user_ids(pid) == set()
    finally:
        hub.close_room(pid)
