"""账号级任务完成：勾选、合并、替换，PVP/PVE 互不影响。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.user import User, UserRole
from app.services.tarkov import task_dones as dones
from app.services.tarkov.game_mode import game_mode_scope


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
    with game_mode_scope("pvp"):
        ids, added = dones.add_done(db, user, "task-1")
        assert added is True
        assert ids == ["task-1"]
        again, added_again = dones.add_done(db, user, "task-1")
        assert added_again is False
        assert again == ["task-1"]
        left, removed = dones.remove_done(db, user, "task-1")
        assert removed is True
        assert left == []
        with pytest.raises(dones.TarkovTaskDonesError):
            dones.add_done(db, user, "  ")


def test_modes_are_isolated() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    now = now_naive()
    dones.add_done(db, user, "pvp-only", game_mode="pvp", now=now)
    dones.add_done(db, user, "pve-only", game_mode="pve", now=now)
    assert dones.list_task_ids(db, user.id, game_mode="pvp") == ["pvp-only"]
    assert dones.list_task_ids(db, user.id, game_mode="pve") == ["pve-only"]


def test_merge_skips_dupes_and_junk() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    with game_mode_scope("pve"):
        dones.add_done(db, user, "keep")
        ids = dones.merge_dones(db, user, ["keep", "new", "", "new", None, "x" * 80])
        assert ids == ["keep", "new"]


def test_replace_rewrites_the_mode_set() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    dones.merge_dones(db, user, ["a", "b"], game_mode="pvp")
    dones.merge_dones(db, user, ["keep-pve"], game_mode="pve")
    ids = dones.replace_dones(db, user, ["b", "c", ""], game_mode="pvp")
    assert ids == ["b", "c"]
    assert dones.list_task_ids(db, user.id, game_mode="pve") == ["keep-pve"]
