"""Raid room WebSocket endpoint: origin check, frame cap, per-event rate limits, eviction."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from app.api.guides import tarkov_raid_rooms as rooms_api
from app.models.user import User, UserRole
from app.services.tarkov import raid_room_ws as room_ws_svc
from app.services.tarkov.raid_room_hub import CLOSE_EVICTED, hub
from app.services.tarkov.ws_limits import CLOSE_TOO_LARGE, TokenBucket


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(rooms_api.router)
    return TestClient(app)


def _frozen() -> float:
    return 0.0


def test_ws_rejects_cross_site_origin_before_auth(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(room_ws_svc, "_load_user", lambda token: calls.append(token))
    with _client().websocket_connect(
        "/raid-rooms/wsorigin1/ws", headers={"origin": "https://evil.example"}
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as caught:
            ws.receive_json()
    assert caught.value.code == 4403
    assert calls == []


def test_ws_closes_oversized_first_frame(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(room_ws_svc, "_load_user", lambda token: calls.append(token))
    with _client().websocket_connect("/raid-rooms/wsbig0001/ws") as ws:
        ws.send_text("x" * (room_ws_svc.MAX_FRAME_CHARS + 1))
        with pytest.raises(WebSocketDisconnect) as caught:
            ws.receive_json()
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
            assert ws.receive_json()["event"] == "snapshot"
            ws.send_json({"event": "view_map", "map_id": "customs"})
            for _ in range(10):
                ws.send_json({"event": "draw_draft", "floor": "", "points": [[1, 2], [3, 4]]})
            ws.send_json({"event": "ping"})
            while ws.receive_json().get("event") != "pong":
                pass
            assert sum(1 for row in published if row.get("event") == "draw_draft") == 3

            hub.evict(pid, user.id)
            last: dict | None = None
            with pytest.raises(WebSocketDisconnect) as caught:
                while True:
                    last = ws.receive_json()
            assert caught.value.code == CLOSE_EVICTED
            assert last == {"event": "member_leave", "user_id": 5}
            assert hub.online_user_ids(pid) == set()
    finally:
        hub.close_room(pid)
