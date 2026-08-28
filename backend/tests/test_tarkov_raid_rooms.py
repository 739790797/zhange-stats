"""Tarkov raid prep rooms: five seats, claims, marks, no archive."""

from __future__ import annotations

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
    assert rooms.normalize_slot_id("abcdef123456") == ""


def test_five_seats_first_joiner_host_and_capacity() -> None:
    db = _session()
    host = _user(db, "host", "房主")
    now = now_naive()
    lobby = rooms.list_live_rooms(db, viewer=host, now=now)
    assert [row["public_id"] for row in lobby["items"]] == ["1", "2", "3", "4", "5"]
    assert all(row["member_count"] == 0 for row in lobby["items"])
    assert all(row["host_user_id"] is None for row in lobby["items"])
    assert all(row["title"] == f"{row['public_id']}号房" for row in lobby["items"])

    created, joined, vacated = rooms.join_room(db, "1", host, now=now)
    assert joined is True
    assert vacated == []
    assert created["is_host"] is True
    assert created["host_user_id"] == host.id
    assert created["map_slug"] == ""
    assert created["can_edit"] is False
    rooms.set_room_map(db, "1", host, "customs", now=now)

    guests = [_user(db, f"u{i}", f"客{i}") for i in range(4)]
    for guest in guests:
        rooms.join_room(db, "1", guest, now=now)
    outsider = _user(db, "out", "路人")
    lobby_all = rooms.list_live_rooms(db, now=now, viewer=outsider)
    assert len(lobby_all["items"]) == 5
    seat = next(row for row in lobby_all["items"] if row["public_id"] == "1")
    assert seat["is_member"] is False
    assert seat["member_count"] == 5
    assert seat["max_members"] == 5
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
    assert snap["marks"] == []
    assert snap["member_count"] == 2
    same = rooms.set_room_map(db, "1", host, "woods", now=now)
    assert same["map_slug"] == "woods"


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
            id=1,
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
            id=1,
            source="test",
            raw_json=json.dumps(pvp_payload),
            note="pvp",
        )
    )
    db.add(
        TarkovTasksRaw(
            id=2,
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
