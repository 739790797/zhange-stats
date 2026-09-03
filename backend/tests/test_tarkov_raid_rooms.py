"""Tarkov raid prep rooms: five seats, claims, marks, no archive."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.user import User, UserRole
from app.services.tarkov import raid_rooms as rooms


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, username: str, display: str) -> User:
    row = User(
        username=username,
        display_name=display,
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def _seat(
    db: Session,
    user: User,
    map_slug: str = "customs",
    slot: str = "1",
    now=None,
) -> dict:
    stamp = now or now_naive()
    rooms.join_room(db, slot, user, now=stamp)
    return rooms.set_room_map(db, slot, user, map_slug, now=stamp)


def test_normalize_room_map_slug() -> None:
    assert rooms.normalize_room_map_slug("streets-of-tarkov") == "streets"
    assert rooms.normalize_room_map_slug("the-lab") == "lab"
    assert rooms.normalize_room_map_slug("factory-night") == "night-factory"
    assert rooms.normalize_room_map_slug("customs") == "customs"
    assert rooms.normalize_room_map_slug("bigmap") == "customs"
    assert rooms.normalize_room_map_slug("Nope!") == ""
    assert rooms.normalize_slot_id("1") == "1"
    assert rooms.normalize_slot_id("5") == "5"
    assert rooms.normalize_slot_id("6") == ""
    assert rooms.normalize_slot_id("pve-1") == "pve-1"
    assert rooms.normalize_slot_id("pve-5") == "pve-5"
    assert rooms.normalize_slot_id("pve-6") == ""
    assert rooms.normalize_slot_id("abcdef123456") == ""
    assert rooms.normalize_public_id("1") == "1"
    assert rooms.normalize_public_id("pve-2") == "pve-2"
    assert rooms.normalize_public_id("ab12cd34") == ""
    assert rooms.slot_public_id(3, "pve") == "pve-3"
    assert rooms.slot_ids_for_mode("pvp") == ("1", "2", "3", "4", "5")
    assert rooms.slot_ids_for_mode("pve") == (
        "pve-1",
        "pve-2",
        "pve-3",
        "pve-4",
        "pve-5",
    )


def test_five_seats_first_joiner_host_and_capacity() -> None:
    db = _session()
    host = _user(db, "host", "房主")
    now = now_naive()
    lobby = rooms.list_live_rooms(db, viewer=host, now=now)
    assert [row["public_id"] for row in lobby["items"]] == ["1", "2", "3", "4", "5"]
    assert all(row["game_mode"] == "pvp" for row in lobby["items"])
    assert all(row["member_count"] == 0 for row in lobby["items"])
    assert all(row["host_user_id"] is None for row in lobby["items"])
    assert all(row["has_password"] is False for row in lobby["items"])
    assert all(row["title"] == f"{i}号房" for i, row in enumerate(lobby["items"], start=1))

    created, joined, vacated = rooms.join_room(db, "1", host, now=now)
    assert joined is True
    assert vacated == []
    assert created["is_host"] is True
    assert created["host_user_id"] == host.id
    assert created["map_slug"] == ""
    assert created["can_edit"] is False
    rooms.set_room_map(db, "1", host, "customs", now=now)

    guests = [_user(db, f"u{i}", f"客{i}") for i in range(rooms.MAX_MEMBERS - 1)]
    for guest in guests:
        rooms.join_room(db, "1", guest, now=now)
    outsider = _user(db, "out", "路人")
    lobby_all = rooms.list_live_rooms(db, now=now, viewer=outsider)
    assert len(lobby_all["items"]) == 5
    seat = next(row for row in lobby_all["items"] if row["public_id"] == "1")
    assert seat["is_member"] is False
    assert seat["member_count"] == rooms.MAX_MEMBERS
    assert seat["max_members"] == rooms.MAX_MEMBERS
    assert [row["display_name"] for row in seat["occupants"]][0] == "房主"
    extra = _user(db, "late", "迟到")
    try:
        rooms.join_room(db, "1", extra, now=now)
        raised = False
    except rooms.RaidRoomError as exc:
        raised = True
        assert exc.status_code == 409
        assert "满" in exc.message
    assert raised


def test_join_other_slot_vacates() -> None:
    db = _session()
    user = _user(db, "p", "甲")
    now = now_naive()
    _seat(db, user, slot="1", now=now)
    snap, joined, vacated = rooms.join_room(db, "2", user, now=now)
    assert joined is True
    assert snap["public_id"] == "2"
    assert snap["is_host"] is True
    assert len(vacated) == 1
    assert vacated[0]["public_id"] == "1"
    assert vacated[0]["member_count"] == 0
    assert vacated[0]["host_user_id"] is None
    assert vacated[0]["map_slug"] == ""
    left = rooms.get_room(db, "1", user, now=now)
    assert left["is_member"] is False
    assert left["member_count"] == 0


def test_host_leave_transfers_last_leave_clears() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.leave_room(db, "1", host, now=now)
    after = rooms.get_room(db, "1", guest, now=now)
    assert after["is_host"] is True
    assert after["host_user_id"] == guest.id
    assert after["map_slug"] == "customs"
    assert after["member_count"] == 1
    rooms.leave_room(db, "1", guest, now=now)
    empty = rooms.get_room(db, "1", guest, now=now)
    assert empty["host_user_id"] is None
    assert empty["map_slug"] == ""
    assert empty["member_count"] == 0
    assert empty["occupants"] == []


def test_reset_host_only() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.claim_task(db, "1", host, "t1", now=now)
    try:
        rooms.reset_room(db, "1", guest, now=now)
        ok = True
    except rooms.RaidRoomError as exc:
        ok = False
        assert exc.status_code == 403
    assert not ok
    snap = rooms.reset_room(db, "1", host, now=now)
    assert snap["host_user_id"] is None
    assert snap["map_slug"] == ""
    assert snap["claims"] == []
    assert snap["members"] == []
    guest_view = rooms.get_room(db, "1", guest, now=now)
    assert guest_view["is_member"] is False


def test_set_map_wipes_board_keeps_members() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.claim_task(db, "1", host, "t1", now=now)
    rooms.bring_key(db, "1", host, "key-a", now=now)
    rooms.mark_objective_done(db, "1", host, "t1", "o1", now=now)
    rooms.add_mark(db, "1", host, kind="pin", floor="", x=1, z=2, now=now)
    try:
        rooms.set_room_map(db, "1", guest, "woods", now=now)
        switched = True
    except rooms.RaidRoomError as exc:
        switched = False
        assert exc.status_code == 403
    assert not switched
    snap = rooms.set_room_map(db, "1", host, "woods", now=now)
    assert snap["map_slug"] == "woods"
    assert snap["claims"] == []
    assert snap["key_brings"] == []
    assert snap["objective_dones"] == []
    assert snap["marks"] == []
    assert snap["member_count"] == 2
    same = rooms.set_room_map(db, "1", host, "woods", now=now)
    assert same["map_slug"] == "woods"


def test_acting_host_can_set_map_when_titled_host_offline() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    first = _user(db, "first", "乙")
    later = _user(db, "later", "丙")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    rooms.join_room(db, "1", first, now=now + timedelta(seconds=1))
    rooms.join_room(db, "1", later, now=now + timedelta(seconds=2))
    rooms.set_room_map(db, "1", host, "customs", now=now)
    from app.models.tarkov import TarkovRaidRoom

    room = db.query(TarkovRaidRoom).filter_by(public_id="1").one()
    seated = rooms._seated_members(db, room.id)
    assert rooms.acting_host_user_id(host.id, seated, {host.id, first.id, later.id}) == host.id
    assert rooms.acting_host_user_id(host.id, seated, {first.id, later.id}) == first.id
    assert rooms.acting_host_user_id(host.id, seated, None) == host.id
    try:
        rooms.set_room_map(
            db,
            "1",
            later,
            "woods",
            now=now,
            online_user_ids={first.id, later.id},
        )
        later_ok = True
    except rooms.RaidRoomError as exc:
        later_ok = False
        assert exc.status_code == 403
    assert later_ok is False
    snap = rooms.set_room_map(
        db,
        "1",
        first,
        "woods",
        now=now,
        online_user_ids={first.id, later.id},
    )
    assert snap["map_slug"] == "woods"
    assert snap["host_user_id"] == host.id


def test_same_raid_id_lets_member_set_map() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    rooms.join_room(db, "1", guest, now=now + timedelta(seconds=1))
    rooms.set_room_map(db, "1", host, "customs", now=now)
    phases = [
        {
            "user_id": host.id,
            "kind": "raid_started",
            "raid_id": "PQXKR6",
            "map_id": "woods",
        },
        {
            "user_id": guest.id,
            "kind": "raid_started",
            "raid_id": "PQXKR6",
            "map_id": "woods",
        },
    ]
    snap = rooms.set_room_map(
        db,
        "1",
        guest,
        "woods",
        now=now,
        online_user_ids={host.id, guest.id},
        log_phases=phases,
    )
    assert snap["map_slug"] == "woods"
    assert snap["host_user_id"] == host.id
    try:
        rooms.set_room_map(
            db,
            "1",
            guest,
            "factory",
            now=now,
            online_user_ids={host.id, guest.id},
            log_phases=phases,
        )
        other_ok = True
    except rooms.RaidRoomError as exc:
        other_ok = False
        assert exc.status_code == 403
    assert other_ok is False


def test_writes_require_map() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    try:
        rooms.claim_task(db, "1", host, "t1", now=now)
        wrote = True
    except rooms.RaidRoomError as exc:
        wrote = False
        assert exc.status_code == 409
        assert "地图" in exc.message
    assert not wrote
    try:
        rooms.bring_key(db, "1", host, "key-a", now=now)
        keyed = True
    except rooms.RaidRoomError as extra_exc:
        keyed = False
        assert extra_exc.status_code == 409
    assert not keyed
    try:
        rooms.mark_objective_done(db, "1", host, "t1", "o1", now=now)
        marked = True
    except rooms.RaidRoomError as extra_exc:
        marked = False
        assert extra_exc.status_code == 409
    assert not marked


def test_claim_rejects_task_not_on_map_when_catalog_present() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    public_id = _seat(db, host, now=now)["public_id"]

    from app.models.tarkov import TarkovTasksRaw
    from app.services.tarkov import tasks as tasks_svc

    CUSTOMS = "56f40101d2720b2a4d8b45d6"
    PRAPOR = "54cb50c76803fa8b248b4571"
    payload = {
        "tasks": {
            "on-customs": {
                "id": "on-customs",
                "name": "On customs",
                "trader": PRAPOR,
                "map": CUSTOMS,
                "objectives": [{"id": "v", "type": "visit", "maps": [CUSTOMS]}],
            }
        },
        "locale": {},
    }
    db.add(
        TarkovTasksRaw(
            mode_id=1,
            lang="",
            source="test",
            raw_json=__import__("json").dumps(payload),
            note="fixture",
        )
    )
    db.flush()
    tasks_svc._raid_prep_cache.clear()

    rooms.claim_task(db, public_id, host, "on-customs", now=now)
    try:
        rooms.claim_task(db, public_id, host, "not-here", now=now)
        raised = False
    except rooms.RaidRoomError as exc:
        raised = True
        assert "本地图" in exc.message
    assert raised


def test_claim_allows_task_present_on_other_game_mode() -> None:
    """列表可能走 PVE raw，认领 ContextVar 默认 PVP，海关任务仍应可勾。"""
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    public_id = _seat(db, host, now=now)["public_id"]

    import json

    from app.models.tarkov import TarkovTasksRaw
    from app.services.tarkov import tasks as tasks_svc

    CUSTOMS = "56f40101d2720b2a4d8b45d6"
    WOODS = "5704e3c2d2720bac5b8b4567"
    PRAPOR = "54cb50c76803fa8b248b4571"
    pvp_payload = {
        "tasks": {
            "woods-only": {
                "id": "woods-only",
                "name": "On woods",
                "trader": PRAPOR,
                "map": WOODS,
                "objectives": [{"id": "v", "type": "visit", "maps": [WOODS]}],
            }
        },
        "locale": {},
    }
    pve_payload = {
        "tasks": {
            "pve-customs": {
                "id": "pve-customs",
                "name": "On customs",
                "trader": PRAPOR,
                "map": CUSTOMS,
                "objectives": [{"id": "v", "type": "visit", "maps": [CUSTOMS]}],
            }
        },
        "locale": {},
    }
    db.add(
        TarkovTasksRaw(
            mode_id=1,
            lang="",
            source="test",
            raw_json=json.dumps(pvp_payload),
            note="pvp",
        )
    )
    db.add(
        TarkovTasksRaw(
            mode_id=2,
            lang="",
            source="test",
            raw_json=json.dumps(pve_payload),
            note="pve",
        )
    )
    db.flush()
    tasks_svc._raid_prep_cache.clear()

    rooms.claim_task(db, public_id, host, "pve-customs", now=now)
    try:
        rooms.claim_task(db, public_id, host, "woods-only", now=now)
        raised = False
    except rooms.RaidRoomError as exc:
        raised = True
        assert "本地图" in exc.message
    assert raised


def test_claim_union_and_unclaim() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    public_id = _seat(db, host, now=now)["public_id"]
    rooms.join_room(db, public_id, guest, now=now)
    rooms.claim_task(db, public_id, host, "t1", now=now)
    rooms.claim_task(db, public_id, guest, "t1", now=now)
    rooms.claim_task(db, public_id, guest, "t2", now=now)
    snap = rooms.get_room(db, public_id, host, now=now)
    names = {(row["task_id"], row["display_name"]) for row in snap["claims"]}
    assert names == {("t1", "甲"), ("t1", "乙"), ("t2", "乙")}
    rooms.unclaim_task(db, public_id, host, "t1", now=now)
    snap = rooms.get_room(db, public_id, host, now=now)
    assert {(row["task_id"], row["user_id"]) for row in snap["claims"]} == {
        ("t1", guest.id),
        ("t2", guest.id),
    }


def test_claim_tasks_batch_dedupes() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    public_id = _seat(db, host, now=now)["public_id"]
    snap, added = rooms.claim_tasks(db, public_id, host, ["t1", "t1", "t2"], now=now)
    assert added == 2
    ids = {row["task_id"] for row in snap["claims"]}
    assert ids == {"t1", "t2"}


def test_marks_undo_and_host_clear() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    public_id = _seat(db, host, map_slug="factory", now=now)["public_id"]
    rooms.join_room(db, public_id, guest, now=now)
    _, pin = rooms.add_mark(
        db, public_id, guest, kind="pin", floor="", x=1, z=2, now=now
    )
    assert pin["kind"] == "pin"
    rooms.add_mark(
        db,
        public_id,
        guest,
        kind="line",
        floor="bunker",
        x=0,
        z=0,
        x2=10,
        z2=0,
        now=now,
    )
    snap, mark_id = rooms.undo_own_mark(db, public_id, guest, now=now)
    assert mark_id is not None
    assert len(snap["marks"]) == 1
    rooms.remove_mark(db, public_id, guest, pin["id"], now=now)
    rooms.add_mark(db, public_id, guest, kind="pin", floor="", x=3, z=4, now=now)
    try:
        rooms.clear_marks(db, public_id, guest, now=now)
        cleared = True
    except rooms.RaidRoomError as extra_exc:
        cleared = False
        assert extra_exc.status_code == 403
    assert not cleared
    snap = rooms.clear_marks(db, public_id, host, now=now)
    assert snap["marks"] == []


def test_stroke_marks_and_draft_parse() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    public_id = _seat(db, host, map_slug="factory", now=now)["public_id"]
    _, stroke = rooms.add_mark(
        db,
        public_id,
        host,
        kind="stroke",
        floor="",
        x=0,
        z=0,
        points=[[0, 0], [4, 1], [8, 2], [12, 2]],
        now=now,
    )
    assert stroke["kind"] == "stroke"
    assert stroke["points"] == [[0.0, 0.0], [4.0, 1.0], [8.0, 2.0], [12.0, 2.0]]
    assert stroke["x2"] == 12.0
    assert stroke["z2"] == 2.0

    try:
        rooms.add_mark(
            db,
            public_id,
            host,
            kind="stroke",
            floor="",
            x=0,
            z=0,
            points=[[0, 0]] * (rooms.MAX_STROKE_POINTS + 1),
            now=now,
        )
        oversized = True
    except rooms.RaidRoomError as extra_exc:
        oversized = False
        assert extra_exc.status_code == 409
    assert not oversized

    try:
        rooms.add_mark(
            db, public_id, host, kind="arrow", floor="", x=1, z=1, now=now
        )
        bad_kind = True
    except rooms.RaidRoomError:
        bad_kind = False
    assert not bad_kind

    assert rooms.parse_draw_draft({"floor": "bunker", "points": []}) == {
        "floor": "bunker",
        "points": [],
    }
    parsed = rooms.parse_draw_draft({"floor": "", "points": [[1, 2], [3, 4]]})
    assert parsed == {"floor": "", "points": [[1.0, 2.0], [3.0, 4.0]]}
    assert rooms.parse_draw_draft({"floor": "", "points": "nope"}) is None
    assert rooms.parse_draw_draft({"floor": "x" * 80, "points": []}) is None

    assert rooms.parse_player_fix(
        {
            "x": 175.301,
            "y": 1.37,
            "z": 150.68,
            "yaw": -12.449,
            "map_id": "streets-of-tarkov",
            "file_name": "2025-03-30[21-04]_175.30.png",
        }
    ) == {
        "x": 175.3,
        "y": 1.37,
        "z": 150.68,
        "yaw": -12.45,
        "map_id": "streets",
        "file_name": "2025-03-30[21-04]_175.30.png",
    }
    assert rooms.parse_player_fix({"x": 1, "y": 2, "z": 3}) == {
        "x": 1.0,
        "y": 2.0,
        "z": 3.0,
        "yaw": None,
        "map_id": "",
        "file_name": "",
    }
    assert rooms.parse_player_fix({"x": 1, "y": 2, "z": "nope"}) is None
    assert rooms.parse_player_fix({"x": 1, "y": 2, "z": 3, "yaw": "bad"}) is None
    assert rooms.parse_log_phase({"kind": "raid_started", "map_id": "bigmap", "raid_id": "ab12cd", "at": "2026-08-31 13:00:00.000", "map_label": "海关"}) == {
        "kind": "raid_started",
        "map_id": "customs",
        "map_label": "海关",
        "raid_id": "AB12CD",
        "at": "2026-08-31 13:00:00.000",
    }
    assert rooms.shared_raid_map_slug(
        2,
        {1, 2},
        [
            {"user_id": 1, "kind": "raid_started", "raid_id": "PQXKR6", "map_id": "woods"},
            {"user_id": 2, "kind": "raid_started", "raid_id": "pqxkr6", "map_id": "woods"},
        ],
    ) == "woods"
    assert rooms.shared_raid_map_slug(
        2,
        {1, 2},
        [{"user_id": 1, "kind": "raid_started", "raid_id": "PQXKR6", "map_id": "woods"}],
    ) == ""
    assert rooms.parse_log_phase({"kind": "nope"}) is None
    assert rooms.parse_log_phase({"kind": "raid_exited", "raid_id": "zz"})["kind"] == "raid_exited"


def test_bring_key_shared_and_toggle() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    room = _seat(db, host, now=now)
    public_id = room["public_id"]
    assert room["key_brings"] == []
    rooms.join_room(db, public_id, guest, now=now)

    snap, added = rooms.bring_key(db, public_id, host, "key-a", now=now)
    assert added is True
    assert snap["key_brings"] == [
        {
            "item_id": "key-a",
            "user_id": host.id,
            "display_name": "甲",
            "created_at": snap["key_brings"][0]["created_at"],
        }
    ]
    again, added_again = rooms.bring_key(db, public_id, host, "key-a", now=now)
    assert added_again is False
    assert len(again["key_brings"]) == 1

    both, guest_added = rooms.bring_key(db, public_id, guest, "key-a", now=now)
    assert guest_added is True
    names = [row["display_name"] for row in both["key_brings"] if row["item_id"] == "key-a"]
    assert names == ["甲", "乙"]

    after, removed = rooms.unbring_key(db, public_id, host, "key-a", now=now)
    assert removed is True
    assert [row["display_name"] for row in after["key_brings"]] == ["乙"]

    try:
        rooms.bring_key(db, public_id, host, "", now=now)
        ok = True
    except rooms.RaidRoomError as exc:
        ok = False
        assert "钥匙" in exc.message
    assert not ok


def test_mark_objective_done_shared_and_toggle() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    room = _seat(db, host, now=now)
    public_id = room["public_id"]
    assert room["objective_dones"] == []
    rooms.join_room(db, public_id, guest, now=now)

    snap, added = rooms.mark_objective_done(
        db, public_id, host, "wet-2", "o-1", now=now
    )
    assert added is True
    assert snap["objective_dones"] == [
        {
            "task_id": "wet-2",
            "objective_id": "o-1",
            "user_id": host.id,
            "display_name": "甲",
            "created_at": snap["objective_dones"][0]["created_at"],
        }
    ]
    again, added_again = rooms.mark_objective_done(
        db, public_id, host, "wet-2", "o-1", now=now
    )
    assert added_again is False
    assert len(again["objective_dones"]) == 1

    both, guest_added = rooms.mark_objective_done(
        db, public_id, guest, "wet-2", "o-1", now=now
    )
    assert guest_added is True
    names = [
        row["display_name"]
        for row in both["objective_dones"]
        if row["task_id"] == "wet-2" and row["objective_id"] == "o-1"
    ]
    assert names == ["甲", "乙"]

    after, removed = rooms.unmark_objective_done(
        db, public_id, host, "wet-2", "o-1", now=now
    )
    assert removed is True
    assert [row["display_name"] for row in after["objective_dones"]] == ["乙"]

    try:
        rooms.mark_objective_done(db, public_id, host, "wet-2", "", now=now)
        ok = True
    except rooms.RaidRoomError as exc:
        ok = False
        assert "目标" in exc.message
    assert not ok


def test_mark_objectives_done_batch() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    room = _seat(db, host, now=now)
    snap, added = rooms.mark_objectives_done(
        db,
        room["public_id"],
        host,
        [("wet-2", "o-1"), ("wet-2", "o-2"), ("wet-2", "o-1")],
        now=now,
    )
    assert added == [("wet-2", "o-1"), ("wet-2", "o-2")]
    assert {
        (row["task_id"], row["objective_id"]) for row in snap["objective_dones"]
    } == {("wet-2", "o-1"), ("wet-2", "o-2")}


def test_host_can_remove_member_and_their_claims() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.claim_task(db, "1", guest, "t-guest", now=now)
    rooms.bring_key(db, "1", guest, "key-b", now=now)
    rooms.mark_objective_done(db, "1", guest, "t-guest", "o-1", now=now)
    snap = rooms.remove_member(db, "1", host, guest.id, now=now)
    assert snap["member_count"] == 1
    assert snap["host_user_id"] == host.id
    assert [row["user_id"] for row in snap["members"]] == [host.id]
    assert snap["claims"] == []
    assert snap["key_brings"] == []
    assert snap["objective_dones"] == []
    guest_view = rooms.get_room(db, "1", guest, now=now)
    assert guest_view["is_member"] is False


def test_remove_member_host_only() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    try:
        rooms.remove_member(db, "1", guest, host.id, now=now)
        ok = True
    except rooms.RaidRoomError as exc:
        ok = False
        assert exc.status_code == 403
    assert not ok
    try:
        rooms.remove_member(db, "1", host, host.id, now=now)
        self_ok = True
    except rooms.RaidRoomError as exc:
        self_ok = False
        assert exc.status_code == 400
    assert not self_ok
    still = rooms.get_room(db, "1", guest, now=now)
    assert still["member_count"] == 2


def test_host_can_transfer_host() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    snap = rooms.transfer_host(db, "1", host, guest.id, now=now)
    assert snap["host_user_id"] == guest.id
    assert snap["host_display_name"] == "乙"
    assert snap["is_host"] is False
    assert snap["is_member"] is True
    guest_view = rooms.get_room(db, "1", guest, now=now)
    assert guest_view["is_host"] is True
    assert guest_view["host_user_id"] == guest.id


def test_transfer_host_host_only() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    outsider = _user(db, "out", "丙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    try:
        rooms.transfer_host(db, "1", guest, host.id, now=now)
        guest_ok = True
    except rooms.RaidRoomError as exc:
        guest_ok = False
        assert exc.status_code == 403
    assert not guest_ok
    try:
        rooms.transfer_host(db, "1", host, host.id, now=now)
        self_ok = True
    except rooms.RaidRoomError as exc:
        self_ok = False
        assert exc.status_code == 400
    assert not self_ok
    try:
        rooms.transfer_host(db, "1", host, outsider.id, now=now)
        out_ok = True
    except rooms.RaidRoomError as exc:
        out_ok = False
        assert exc.status_code == 404
    assert not out_ok
    still = rooms.get_room(db, "1", host, now=now)
    assert still["host_user_id"] == host.id
    assert still["member_count"] == 2


def test_room_password_gates_join_and_clears_when_empty() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    other = _user(db, "other", "丙")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    locked = rooms.set_room_password(db, "1", host, "secret", now=now)
    assert locked["has_password"] is True
    assert "password_hash" not in locked
    lobby = rooms.list_live_rooms(db, viewer=guest, now=now, game_mode="pvp")
    assert "private" not in lobby
    seat = next(row for row in lobby["items"] if row["public_id"] == "1")
    assert seat["has_password"] is True
    rooms.join_room(db, "2", guest, now=now)
    try:
        rooms.join_room(db, "1", guest, now=now)
        missing = True
    except rooms.RaidRoomError as exc:
        missing = False
        assert exc.status_code == 403
        assert "密码" in exc.message
    assert not missing
    still = rooms.get_room(db, "2", guest, now=now)
    assert still["is_member"] is True
    try:
        rooms.join_room(db, "1", guest, now=now, password="wrong")
        wrong = True
    except rooms.RaidRoomError as extra_exc:
        wrong = False
        assert extra_exc.status_code == 403
    assert not wrong
    still_two = rooms.get_room(db, "2", guest, now=now)
    assert still_two["is_member"] is True
    joined, added, vacated = rooms.join_room(
        db, "1", guest, now=now, password="secret"
    )
    assert added is True
    assert joined["is_member"] is True
    assert vacated
    again, added_again, _vacated = rooms.join_room(db, "1", host, now=now)
    assert added_again is False
    assert again["is_member"] is True
    try:
        rooms.set_room_password(db, "1", guest, "nope", now=now)
        guest_ok = True
    except rooms.RaidRoomError as guest_exc:
        guest_ok = False
        assert guest_exc.status_code == 403
    assert not guest_ok
    rooms.set_room_password(db, "1", host, "", now=now)
    cleared = rooms.get_room(db, "1", host, now=now)
    assert cleared["has_password"] is False
    rooms.set_room_password(db, "1", host, "again", now=now)
    rooms.leave_room(db, "1", host, now=now)
    rooms.leave_room(db, "1", guest, now=now)
    empty = rooms.list_live_rooms(db, viewer=other, now=now, game_mode="pvp")
    empty_seat = next(row for row in empty["items"] if row["public_id"] == "1")
    assert empty_seat["has_password"] is False
    snap, added_empty, _vacated2 = rooms.join_room(db, "1", other, now=now)
    assert added_empty is True
    assert snap["is_host"] is True
    assert snap["has_password"] is False


def test_reset_clears_room_password() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    rooms.set_room_password(db, "1", host, "keep", now=now)
    rooms.reset_room(db, "1", host, now=now)
    lobby = rooms.list_live_rooms(db, viewer=host, now=now, game_mode="pvp")
    seat = next(row for row in lobby["items"] if row["public_id"] == "1")
    assert seat["has_password"] is False
    snap, added, _vacated = rooms.join_room(db, "1", host, now=now)
    assert added is True
    assert snap["has_password"] is False


def test_join_empty_slot_keeps_fixed_mode() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    snap, joined, _vacated = rooms.join_room(
        db, "2", host, now=now, game_mode="pve"
    )
    assert joined is True
    assert snap["game_mode"] == "pvp"
    try:
        rooms.set_room_game_mode(db, "2", host, "pve", now=now)
        changed = True
    except rooms.RaidRoomError as extra_exc:
        changed = False
        assert extra_exc.status_code == 403
    assert not changed
    pve, pve_joined, _vacated2 = rooms.join_room(
        db, "pve-2", host, now=now, game_mode="pvp"
    )
    assert pve_joined is True
    assert pve["game_mode"] == "pve"
    assert pve["title"] == "2号房"


def test_lobby_lists_only_current_mode_slots() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    from app.services.tarkov.game_mode import game_mode_scope

    rooms.join_room(db, "1", host, now=now)
    pvp = rooms.list_live_rooms(db, viewer=host, now=now, game_mode="pvp")
    assert [row["public_id"] for row in pvp["items"]] == ["1", "2", "3", "4", "5"]
    assert pvp["items"][0]["is_member"] is True
    with game_mode_scope("pve"):
        pve = rooms.list_live_rooms(db, viewer=host, now=now)
    assert [row["public_id"] for row in pve["items"]] == [
        "pve-1",
        "pve-2",
        "pve-3",
        "pve-4",
        "pve-5",
    ]
    assert all(row["game_mode"] == "pve" for row in pve["items"])
    assert all(row["is_member"] is False for row in pve["items"])
    assert all(row["title"] == f"{i}号房" for i, row in enumerate(pve["items"], start=1))


def test_room_claims_allow_multiple_members() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.claim_task(db, "1", host, "t1", now=now)
    snap, added = rooms.claim_task(db, "1", guest, "t1", now=now)
    assert added is True
    owners = [
        row["user_id"]
        for row in snap["claims"]
        if row["task_id"] == "t1"
    ]
    assert set(owners) == {host.id, guest.id}


def test_stale_member_pruned_when_offline() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    almost = now + timedelta(seconds=rooms.MEMBER_IDLE_SECONDS - 1)
    still = rooms.get_room(
        db, "1", host, now=almost, online_user_ids={host.id}
    )
    assert guest.id in [row["user_id"] for row in still["occupants"]]
    later = now + timedelta(seconds=rooms.MEMBER_IDLE_SECONDS + 60)
    snap = rooms.get_room(
        db, "1", host, now=later, online_user_ids={host.id}
    )
    assert snap["member_count"] == 1
    assert [row["user_id"] for row in snap["occupants"]] == [host.id]
    rooms.join_room(db, "1", guest, now=later)
    rooms.touch_member(db, "1", guest, now=later)
    kept = rooms.get_room(
        db,
        "1",
        host,
        now=later + timedelta(seconds=rooms.MEMBER_IDLE_SECONDS + 60),
        online_user_ids={guest.id},
    )
    assert guest.id in [row["user_id"] for row in kept["occupants"]]


def test_ws_online_keeps_member_even_if_last_seen_is_old() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    later = now + timedelta(hours=5)
    snap = rooms.get_room(
        db, "1", host, now=later, online_user_ids={host.id, guest.id}
    )
    assert {row["user_id"] for row in snap["occupants"]} == {host.id, guest.id}


def test_get_room_is_not_a_heartbeat() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    mid = now + timedelta(seconds=rooms.MEMBER_IDLE_SECONDS - 60)
    mid_snap = rooms.get_room(db, "1", guest, now=mid, online_user_ids=set())
    assert mid_snap["is_member"] is True
    later = now + timedelta(seconds=rooms.MEMBER_IDLE_SECONDS + 60)
    kicked = rooms.get_room(
        db, "1", guest, now=later, online_user_ids={host.id}
    )
    assert kicked["is_member"] is False
    host_snap = rooms.get_room(
        db, "1", host, now=later, online_user_ids={host.id}
    )
    assert host_snap["is_member"] is True
    assert guest.id not in [row["user_id"] for row in host_snap["occupants"]]


def test_active_started_ids_drops_done() -> None:
    assert rooms.active_started_ids(["a", "b", "c"], ["b", "d"]) == ["a", "c"]
    assert rooms.active_started_ids(["a", "a"], []) == ["a"]


def test_build_raid_room_map_overlap_ranks_coverage() -> None:
    catalogs = {
        "customs": {
            "t1": {"name": "A", "trader_slug": "prapor"},
            "t2": "B",
            "t3": "C",
        },
        "woods": {"t1": "A", "t9": "Z"},
    }
    occupants = [
        {"user_id": 1, "uploaded": True, "started_ids": ["t1", "t2"]},
        {"user_id": 2, "uploaded": True, "started_ids": ["t1", "t9"]},
        {"user_id": 3, "uploaded": False, "started_ids": ["t1"]},
    ]
    rows = rooms.build_raid_room_map_overlap(
        occupants, catalogs, ["customs", "woods"]
    )
    by_slug = {row["map_slug"]: row for row in rows}
    customs = by_slug["customs"]
    woods = by_slug["woods"]
    assert customs["with_tasks_count"] == 2
    assert woods["with_tasks_count"] == 2
    assert [cell["count"] for cell in customs["cells"]] == [2, 1, 0]
    assert by_slug["customs"]["cells"][2]["uploaded"] is False
    assert "overlap_count" not in customs
    assert "all_have" not in customs
    assert rows[0]["map_slug"] == "customs"
    shared = [t for t in customs["tasks"] if t["id"] == "t1"][0]
    assert shared["user_ids"] == [1, 2]
    assert shared["trader_slug"] == "prapor"
    named = [t for t in customs["tasks"] if t["id"] == "t2"][0]
    assert named["name"] == "B"
    assert named["trader_slug"] == ""


def test_set_member_task_progress_marks_uploaded() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    empty = rooms.get_room(db, "1", host, now=now)
    assert all(not row["uploaded"] for row in empty["task_progress"])
    snap = rooms.set_member_task_progress(
        db, "1", host, ["t1", "t2"], ["t2"], now=now
    )
    mine = next(row for row in snap["task_progress"] if row["user_id"] == host.id)
    other = next(row for row in snap["task_progress"] if row["user_id"] == guest.id)
    assert mine["uploaded"] is True
    assert mine["started_count"] == 1
    assert other["uploaded"] is False
    guest_snap = rooms.set_member_task_progress(
        db, "1", guest, ["t1"], [], now=now
    )
    assert isinstance(guest_snap["map_overlap"], list)


def test_member_task_progress_count_hides_ids_missing_from_catalog(
    monkeypatch,
) -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    rooms.join_room(db, "1", host, now=now)
    rooms.set_member_task_progress(db, "1", host, ["keep", "gone"], [], now=now)
    monkeypatch.setattr(
        "app.services.tarkov.tasks.catalog_task_id_set",
        lambda _db: {"keep"},
    )
    snap = rooms.get_room(db, "1", host, now=now)
    mine = next(row for row in snap["task_progress"] if row["user_id"] == host.id)
    assert mine["started_count"] == 1


def test_seed_claims_from_progress_host_only() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.set_member_task_progress(db, "1", host, ["t-host"], [], now=now)
    rooms.set_member_task_progress(db, "1", guest, ["t-guest"], [], now=now)
    try:
        rooms.seed_claims_from_progress(db, "1", guest, now=now)
        ok = True
    except rooms.RaidRoomError as exc:
        ok = False
        assert exc.status_code == 403
    assert not ok
    snap, added = rooms.seed_claims_from_progress(db, "1", host, now=now)
    # no tasks raw → catalog empty, nothing claimed
    assert added == 0
    assert snap["claims"] == []


def test_seed_claims_from_progress_uses_catalog(monkeypatch) -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    _seat(db, host, now=now)
    rooms.join_room(db, "1", guest, now=now)
    rooms.set_member_task_progress(db, "1", host, ["t-host", "skip"], [], now=now)
    rooms.set_member_task_progress(db, "1", guest, ["t-guest"], [], now=now)

    def _index(_db):
        return {"customs": {"t-host": "H", "t-guest": "G"}}

    monkeypatch.setattr(
        "app.services.tarkov.tasks.raid_prep_map_task_index",
        _index,
    )
    snap, added = rooms.seed_claims_from_progress(db, "1", host, now=now)
    assert added == 2
    ids = {(row["task_id"], row["user_id"]) for row in snap["claims"]}
    assert ("t-host", host.id) in ids
    assert ("t-guest", guest.id) in ids
    assert ("skip", host.id) not in ids
