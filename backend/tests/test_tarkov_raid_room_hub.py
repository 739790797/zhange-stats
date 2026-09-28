"""Raid room hub: in-memory screenshot positions for late-joining devices."""

import asyncio

from app.services.tarkov.raid_room_hub import RaidRoomHub


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
