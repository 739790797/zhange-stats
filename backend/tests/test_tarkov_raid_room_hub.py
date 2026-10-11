"""Raid room hub: in-memory screenshot positions for late-joining devices."""

import asyncio
import functools

from app.services.tarkov import raid_room_hub as hub_mod
from app.services.tarkov import ws_limits
from app.services.tarkov.raid_room_hub import RaidRoomHub


class _FakeSocket:
    def __init__(self, *, stall: bool = False) -> None:
        self.sent: list[dict] = []
        self.closed: int | None = None
        self.stall = stall

    async def send_json(self, payload: dict) -> None:
        if self.stall:
            await asyncio.sleep(3600)
        if self.closed is not None:
            raise RuntimeError("closed")
        self.sent.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.closed = code


async def _drain(hub: RaidRoomHub) -> None:
    for _ in range(20):
        await asyncio.sleep(0)
        pending = list(hub._tasks)
        if pending:
            await asyncio.gather(*pending)


def test_hub_remembers_player_fix_for_snapshot() -> None:
    hub = RaidRoomHub()
    stored = hub.set_player_fix(
        "abc12345",
        12,
        {
            "x": 175.3,
            "y": 1.37,
            "z": 150.68,
            "yaw": -12.45,
            "map_id": "customs",
            "file_name": "shot.png",
        },
    )
    assert stored["user_id"] == 12
    assert stored["x"] == 175.3
    assert stored["map_id"] == "customs"
    assert isinstance(stored["at"], int) and stored["at"] > 0
    rows = hub.player_fixes("abc12345")
    assert len(rows) == 1
    assert rows[0]["user_id"] == 12
    assert rows[0]["file_name"] == "shot.png"

    hub.set_player_fix("abc12345", 3, {"x": 1, "y": 2, "z": 3, "map_id": "customs"})
    hub.drop_offline_player_fixes("abc12345", {12})
    left = hub.player_fixes("abc12345")
    assert [row["user_id"] for row in left] == [12]

    hub.drop_offline_player_fixes("abc12345", set())
    assert hub.player_fixes("abc12345") == []


def test_user_stays_online_while_either_client_is_connected() -> None:
    hub = RaidRoomHub()
    web = object()
    desktop = object()

    async def run() -> None:
        await hub.join("room", web, 7, "web")  # type: ignore[arg-type]
        await hub.join("room", desktop, 7, "desktop")  # type: ignore[arg-type]
        assert hub.online_user_ids("room") == {7}
        assert hub.online_clients("room") == [{"user_id": 7, "clients": ["desktop", "web"]}]
        left = await hub.leave("room", web)  # type: ignore[arg-type]
        assert left == {7}
        assert hub.online_clients("room") == [{"user_id": 7, "clients": ["desktop"]}]
        await hub.leave("room", desktop)  # type: ignore[arg-type]
        assert hub.online_user_ids("room") == set()
        assert hub.online_clients("room") == []
        page_a = object()
        page_b = object()
        await hub.join("room", page_a, 7, "web")  # type: ignore[arg-type]
        await hub.join("room", page_b, 7, "web")  # type: ignore[arg-type]
        assert hub.online_clients("room") == [{"user_id": 7, "clients": ["web", "web"]}]
        await hub.leave("room", page_a)  # type: ignore[arg-type]
        assert hub.online_clients("room") == [{"user_id": 7, "clients": ["web"]}]

    asyncio.run(run())


def test_evict_from_worker_thread_stops_broadcasts_then_closes() -> None:
    hub = RaidRoomHub()
    stay = _FakeSocket()
    gone_web = _FakeSocket()
    gone_desktop = _FakeSocket()

    async def run() -> None:
        await hub.join("room", stay, 7, "web")  # type: ignore[arg-type]
        await hub.join("room", gone_web, 8, "web")  # type: ignore[arg-type]
        await hub.join("room", gone_desktop, 8, "desktop")  # type: ignore[arg-type]
        hub.set_view_map("room", 8, "customs")
        hub.set_log_phase("room", 8, {"kind": "raid_started", "map_id": "customs"})
        hub.set_player_fix("room", 8, {"x": 1, "y": 2, "z": 3, "map_id": "customs"})

        evicted = await asyncio.to_thread(hub.evict, "room", 8)
        assert evicted == 2
        assert not hub.is_connected("room", gone_web)  # type: ignore[arg-type]
        assert hub.online_user_ids("room") == {7}
        assert hub.view_map_of("room", 8) == ""
        assert hub.log_phases("room") == []
        assert hub.player_fixes("room") == []

        await hub.broadcast("room", {"event": "claim_add"})
        await _drain(hub)
        assert [row["event"] for row in stay.sent] == ["claim_add"]
        for ws in (gone_web, gone_desktop):
            assert ws.sent == [{"event": "member_leave", "user_id": 8}]
            assert ws.closed == hub_mod.CLOSE_EVICTED

    asyncio.run(run())


def test_close_room_sends_final_event_and_forgets_room_state() -> None:
    hub = RaidRoomHub()
    a = _FakeSocket()
    b = _FakeSocket()

    async def run() -> None:
        await hub.join("room", a, 7)  # type: ignore[arg-type]
        await hub.join("room", b, 8)  # type: ignore[arg-type]
        hub.set_view_map("room", 7, "woods")
        hub.set_log_phase("room", 8, {"kind": "matching"})
        await hub.broadcast("room", {"event": "presence"})
        assert hub.close_room("room", payload={"event": "reset"}) == 2
        assert "room" not in hub.known_public_ids()
        assert hub.view_maps("room") == []
        assert hub.log_phases("room") == []
        assert "room" not in hub._seq
        await _drain(hub)
        for ws in (a, b):
            assert ws.sent[-1] == {"event": "reset"}
            assert ws.closed == hub_mod.CLOSE_ROOM_GONE

    asyncio.run(run())


def test_last_socket_leaving_forgets_per_room_dicts() -> None:
    hub = RaidRoomHub()
    ws = _FakeSocket()

    async def run() -> None:
        await hub.join("room", ws, 7)  # type: ignore[arg-type]
        hub.set_view_map("room", 7, "woods")
        hub.set_log_phase("room", 7, {"kind": "matching"})
        hub.set_player_fix("room", 7, {"x": 1, "y": 2, "z": 3, "map_id": "woods"})
        await hub.broadcast("room", {"event": "presence"})
        assert hub._seq["room"] == 1
        await hub.leave("room", ws)  # type: ignore[arg-type]
        for bucket in (hub._rooms, hub._seq, hub._log_phases, hub._view_maps, hub._player_fixes):
            assert "room" not in bucket

    asyncio.run(run())


def test_broadcast_drops_socket_that_cannot_keep_up(monkeypatch) -> None:
    monkeypatch.setattr(
        hub_mod,
        "send_json_timeout",
        functools.partial(ws_limits.send_json_timeout, timeout=0.05),
    )
    hub = RaidRoomHub()
    fast = _FakeSocket()
    slow = _FakeSocket(stall=True)

    async def run() -> None:
        await hub.join("room", fast, 7)  # type: ignore[arg-type]
        await hub.join("room", slow, 8)  # type: ignore[arg-type]
        await asyncio.wait_for(hub.broadcast("room", {"event": "presence"}), timeout=2)
        assert [row["event"] for row in fast.sent] == ["presence"]
        assert hub.online_user_ids("room") == {7}
        assert slow.closed == hub_mod.CLOSE_SLOW_CONSUMER

    asyncio.run(run())


def test_broadcast_to_room_without_sockets_keeps_no_state() -> None:
    hub = RaidRoomHub()

    async def run() -> None:
        await hub.broadcast("nobody", {"event": "presence"})
        hub.publish("nobody", {"event": "presence"})
        await _drain(hub)

    asyncio.run(run())
    assert "nobody" not in hub._seq
    assert hub.known_public_ids() == set()


def test_publish_from_worker_thread_keeps_order() -> None:
    hub = RaidRoomHub()
    ws = _FakeSocket()

    async def run() -> None:
        await hub.join("room", ws, 7)  # type: ignore[arg-type]

        def burst() -> None:
            for n in range(5):
                hub.publish("room", {"event": "mark_add", "n": n})

        await asyncio.to_thread(burst)
        await _drain(hub)
        assert [row["n"] for row in ws.sent] == [0, 1, 2, 3, 4]
        assert [row["seq"] for row in ws.sent] == [1, 2, 3, 4, 5]

    asyncio.run(run())
