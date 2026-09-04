"""账号级钥匙拥有：勾选、合并、按用户列出。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.user import User, UserRole
from app.services.tarkov import key_owns as owns
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


def test_add_remove_and_reject_blank() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    ids, added = owns.add_own(db, user, "key-1")
    assert added is True
    assert ids == ["key-1"]
    again, added_again = owns.add_own(db, user, "key-1")
    assert added_again is False
    assert again == ["key-1"]
    left, removed = owns.remove_own(db, user, "key-1")
    assert removed is True
    assert left == []
    with pytest.raises(owns.TarkovKeyOwnsError):
        owns.add_own(db, user, "  ")


def test_merge_skips_dupes_and_junk() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    owns.add_own(db, user, "keep")
    ids = owns.merge_owns(db, user, ["keep", "new", "", "new", None, "x" * 80])
    assert ids == ["keep", "new"]


def test_room_snapshot_lists_seated_owns() -> None:
    db = _session()
    host = _user(db, "host", "甲")
    guest = _user(db, "guest", "乙")
    outsider = _user(db, "out", "路人")
    now = now_naive()
    owns.add_own(db, host, "key-a", now=now)
    owns.add_own(db, guest, "key-a", now=now)
    owns.add_own(db, guest, "key-b", now=now)
    owns.add_own(db, outsider, "key-a", now=now)
    created, _joined, _vacated = rooms.create_room(db, host, now=now)
    pid = created["public_id"]
    rooms.set_room_map(db, pid, host, "customs", now=now)
    rooms.join_room(db, pid, guest, now=now)
    snap = rooms.get_room(db, pid, host)
    names = {
        (row["item_id"], row["display_name"]) for row in snap["key_owns"]
    }
    assert names == {("key-a", "甲"), ("key-a", "乙"), ("key-b", "乙")}
    assert rooms.occupant_public_ids(db, host.id) == [pid]
    assert rooms.occupant_public_ids(db, outsider.id) == []
