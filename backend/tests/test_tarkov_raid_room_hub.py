"""Raid room hub: in-memory screenshot positions for late-joining devices."""

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
