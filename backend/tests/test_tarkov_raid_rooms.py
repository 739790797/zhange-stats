"""Tarkov raid prep rooms: lobby, claims, marks, 24h archive."""

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


def test_normalize_room_map_slug() -> None:
    assert rooms.normalize_room_map_slug("streets-of-tarkov") == "streets"
    assert rooms.normalize_room_map_slug("the-lab") == "lab"
    assert rooms.normalize_room_map_slug("factory-night") == "night-factory"
    assert rooms.normalize_room_map_slug("customs") == "customs"
    assert rooms.normalize_room_map_slug("Nope!") == ""


def test_create_join_lobby_and_capacity() -> None:
    db = _session()
    host = _user(db, "host", "房主")
    now = now_naive()
    created = rooms.create_room(db, host, map_slug="customs", now=now)
    assert created["status"] == "live"
    assert created["map_slug"] == "customs"
    assert created["is_host"] is True
    assert created["member_count"] == 1
    public_id = created["public_id"]

    lobby = rooms.list_live_rooms(db, map_slug="customs", now=now, viewer=host)
    assert len(lobby["items"]) == 1
    assert lobby["items"][0]["public_id"] == public_id
    assert lobby["items"][0]["is_member"] is True

    guests = [_user(db, f"u{i}", f"客{i}") for i in range(7)]
    for guest in guests:
        rooms.join_room(db, public_id, guest, now=now)
    outsider = _user(db, "out", "路人")
    lobby_out = rooms.list_live_rooms(db, map_slug="customs", now=now, viewer=outsider)
    assert lobby_out["items"][0]["is_member"] is False
    lobby_guest = rooms.list_live_rooms(db, map_slug="customs", now=now, viewer=guests[0])
    assert lobby_guest["items"][0]["is_member"] is True
    extra = _user(db, "late", "迟到")
    try:
        rooms.join_room(db, public_id, extra, now=now)
        raised = False
    except rooms.RaidRoomError as exc:
        raised = True
        assert exc.status_code == 409
        assert "满" in exc.message
    assert raised

    second = _user(db, "host2", "二号")
    try:
        rooms.create_room(db, host, map_slug="woods", now=now)
        hosted = False
    except rooms.RaidRoomError as exc:
        hosted = True
        assert exc.status_code == 409
    assert hosted
    rooms.create_room(db, second, map_slug="woods", now=now)


def test_claim_union_and_unclaim() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    room = rooms.create_room(db, host, map_slug="customs", now=now)
    public_id = room["public_id"]
    rooms.join_room(db, public_id, guest, now=now)
    rooms.claim_task(db, public_id, host, "t1", now=now)
    rooms.claim_task(db, public_id, guest, "t1", now=now)
    rooms.claim_task(db, public_id, guest, "t2", now=now)
    snap, _ = rooms.get_room(db, public_id, host, now=now)
    names = {(row["task_id"], row["display_name"]) for row in snap["claims"]}
    assert names == {("t1", "甲"), ("t1", "乙"), ("t2", "乙")}
    rooms.unclaim_task(db, public_id, host, "t1", now=now)
    snap, _ = rooms.get_room(db, public_id, host, now=now)
    assert {(row["task_id"], row["user_id"]) for row in snap["claims"]} == {
        ("t1", guest.id),
        ("t2", guest.id),
    }


def test_marks_undo_and_host_clear() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    room = rooms.create_room(db, host, map_slug="factory", now=now)
    public_id = room["public_id"]
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
    room = rooms.create_room(db, host, map_slug="factory", now=now)
    public_id = room["public_id"]
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


def test_expire_archives_and_rejects_writes() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    now = now_naive()
    room = rooms.create_room(db, host, map_slug="customs", now=now)
    public_id = room["public_id"]
    later = now + timedelta(hours=24, minutes=1)
    snap, archived_now = rooms.get_room(db, public_id, host, now=later)
    assert archived_now is True
    assert snap["status"] == "archived"
    assert snap["can_edit"] is False
    lobby = rooms.list_live_rooms(db, now=later)
    assert lobby["items"] == []
    try:
        rooms.claim_task(db, public_id, host, "t1", now=later)
        wrote = True
    except rooms.RaidRoomError as exc:
        wrote = False
        assert exc.status_code == 409
    assert not wrote
    closed = rooms.close_room(db, public_id, host, now=later)
    assert closed["status"] == "archived"


def test_host_close_before_expiry() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    now = now_naive()
    room = rooms.create_room(db, host, map_slug="customs", now=now)
    public_id = room["public_id"]
    rooms.join_room(db, public_id, guest, now=now)
    try:
        rooms.close_room(db, public_id, guest, now=now)
        ok = True
    except rooms.RaidRoomError as exc:
        ok = False
        assert exc.status_code == 403
    assert not ok
    snap = rooms.close_room(db, public_id, host, now=now)
    assert snap["status"] == "archived"
    try:
        rooms.join_room(db, public_id, guest, now=now)
        joined = True
    except rooms.RaidRoomError as exc:
        joined = False
        assert exc.status_code == 409
    assert not joined
