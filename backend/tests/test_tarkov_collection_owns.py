"""账号级 3×4 收集勾选：按 PVP/PVE 分开。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.user import User, UserRole
from app.services.tarkov import collection_owns as owns
from app.services.tarkov.game_mode import use_game_mode, reset_game_mode


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, username: str) -> User:
    row = User(
        username=username,
        display_name=username,
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def test_add_remove_and_reject_blank() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pvp")
    try:
        ids, added = owns.add_own(db, user, "item-1")
        assert added is True
        assert ids == ["item-1"]
        again, added_again = owns.add_own(db, user, "item-1")
        assert added_again is False
        assert again == ["item-1"]
        left, removed = owns.remove_own(db, user, "item-1")
        assert removed is True
        assert left == []
        with pytest.raises(owns.TarkovCollectionOwnsError):
            owns.add_own(db, user, "  ")
    finally:
        reset_game_mode(token)


def test_pvp_and_pve_are_separate() -> None:
    db = _session()
    user = _user(db, "a")
    pvp = use_game_mode("pvp")
    try:
        owns.add_own(db, user, "pvp-only")
    finally:
        reset_game_mode(pvp)
    pve = use_game_mode("pve")
    try:
        owns.add_own(db, user, "pve-only")
        assert owns.list_item_ids(db, user.id) == ["pve-only"]
    finally:
        reset_game_mode(pve)
    assert owns.list_item_ids(db, user.id, game_mode="pvp") == ["pvp-only"]


def test_merge_skips_dupes_and_junk() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pve")
    try:
        owns.add_own(db, user, "keep")
        ids = owns.merge_owns(db, user, ["keep", "new", "", "new", None, "x" * 80])
        assert ids == ["keep", "new"]
    finally:
        reset_game_mode(token)


def test_replace_owns_drops_missing() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pvp")
    try:
        owns.add_own(db, user, "old")
        owns.add_own(db, user, "keep")
        ids = owns.replace_owns(db, user, ["keep", "new", ""])
        assert ids == ["keep", "new"]
    finally:
        reset_game_mode(token)
