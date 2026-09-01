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


def test_merge_progress_keeps_account_rows() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    dones.write_progress(
        db,
        user,
        ["old-done", "shared"],
        ["old-start"],
        replace=True,
        game_mode="pvp",
    )
    done, started = dones.write_progress(
        db,
        user,
        ["raid-done"],
        ["raid-start"],
        replace=False,
        game_mode="pvp",
    )
    assert done == ["old-done", "shared", "raid-done"]
    assert started == ["old-start", "raid-start"]


def test_started_is_account_ledger_and_done_wins() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    dones.merge_starteds(db, user, ["s1", "s2", "done-later"], game_mode="pvp")
    dones.merge_starteds(db, user, ["pve-s"], game_mode="pve")
    assert dones.list_started_ids(db, user.id, game_mode="pvp") == [
        "done-later",
        "s1",
        "s2",
    ]
    dones.add_done(db, user, "done-later", game_mode="pvp")
    done, started = dones.list_progress(db, user.id, game_mode="pvp")
    assert done == ["done-later"]
    assert started == ["s1", "s2"]
    assert dones.list_started_ids(db, user.id, game_mode="pve") == ["pve-s"]


def test_write_progress_replace_and_merge_started() -> None:
    db = _session()
    user = _user(db, "a", "甲")
    done, started = dones.write_progress(
        db,
        user,
        ["d1"],
        ["s1", "d1"],
        replace=True,
        game_mode="pvp",
    )
    assert done == ["d1"]
    assert started == ["s1"]
    done, started = dones.write_progress(
        db,
        user,
        ["d2"],
        ["s2"],
        replace=False,
        game_mode="pvp",
    )
    assert done == ["d1", "d2"]
    assert started == ["s1", "s2"]
    done, started = dones.write_progress(
        db,
        user,
        ["d2"],
        None,
        replace=True,
        game_mode="pvp",
    )
    assert done == ["d2"]
    assert started == ["s1", "s2"]
    done, started = dones.write_progress(
        db,
        user,
        ["d2"],
        [],
        replace=True,
        game_mode="pvp",
    )
    assert done == ["d2"]
    assert started == []
