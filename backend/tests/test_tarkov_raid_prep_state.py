"""联机大厅单人准备账号落盘：勾选、目标完成、钥匙声明。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.user import User, UserRole
from app.services.tarkov import raid_prep_state as prep
from app.services.tarkov.game_mode import game_mode_scope


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session) -> User:
    row = User(
        username="a",
        display_name="甲",
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def test_empty_then_put_and_get() -> None:
    db = _session()
    user = _user(db)
    now = now_naive()
    with game_mode_scope("pvp"):
        empty = prep.get_state(db, user, "customs")
        assert empty["selected"] == []
        assert empty["key_brings"] == []
        saved = prep.put_state(
            db,
            user,
            "customs",
            selected=["t1", "t1", "t2"],
            objective_dones=[
                {"task_id": "t1", "objective_id": "o1"},
                {"task_id": "t1", "objective_id": "o1"},
            ],
            key_brings=["key-a"],
            now=now,
        )
        assert saved["selected"] == ["t1", "t2"]
        assert saved["objective_dones"] == [
            {"task_id": "t1", "objective_id": "o1"}
        ]
        assert saved["key_brings"] == ["key-a"]
        again = prep.get_state(db, user, "customs")
        assert again["selected"] == ["t1", "t2"]


def test_modes_and_maps_are_isolated() -> None:
    db = _session()
    user = _user(db)
    prep.put_state(db, user, "customs", selected=["pvp-c"], game_mode="pvp")
    prep.put_state(db, user, "woods", selected=["pvp-w"], game_mode="pvp")
    prep.put_state(db, user, "customs", selected=["pve-c"], game_mode="pve")
    assert prep.get_state(db, user, "customs", game_mode="pvp")["selected"] == [
        "pvp-c"
    ]
    assert prep.get_state(db, user, "woods", game_mode="pvp")["selected"] == [
        "pvp-w"
    ]
    assert prep.get_state(db, user, "customs", game_mode="pve")["selected"] == [
        "pve-c"
    ]


def test_invalid_map_rejected() -> None:
    db = _session()
    user = _user(db)
    with pytest.raises(prep.TarkovRaidPrepStateError):
        prep.get_state(db, user, "Nope!")
