"""联机大厅单人准备账号落盘：勾选、目标完成、钥匙声明。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserRaidPrep
from app.models.user import User, UserRole
from app.api.guides.schemas import TarkovUserRaidPrepStateIn
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


def test_unknown_but_wellformed_map_slug_rejected() -> None:
    """只归一化不校验的话，任何形似 slug 的串都能在库里落一行。"""
    db = _session()
    user = _user(db)
    for bad in ("fake-map", "not-a-real-map", "ab12cd34"):
        with pytest.raises(prep.TarkovRaidPrepStateError) as caught:
            prep.put_state(db, user, bad, selected=["t1"])
        assert caught.value.status_code == 400
        with pytest.raises(prep.TarkovRaidPrepStateError):
            prep.get_state(db, user, bad)
    assert db.query(TarkovUserRaidPrep).count() == 0


def test_known_room_map_slugs_accepted() -> None:
    """归一化后的短 id（含等价写法）照常收：the-lab -> lab、streets-of-tarkov -> streets。"""
    db = _session()
    user = _user(db)
    for raw, expected in (
        ("customs", "customs"),
        ("the-lab", "lab"),
        ("streets-of-tarkov", "streets"),
        ("factory-night", "night-factory"),
    ):
        saved = prep.put_state(db, user, raw, selected=["t1"])
        assert saved["map"] == expected


def test_state_in_clips_oversize_and_drops_invalid() -> None:
    body = TarkovUserRaidPrepStateIn.model_validate(
        {
            "selected": [f"t{i}" for i in range(50)],
            "objective_dones": [
                {"task_id": f"t{i}", "objective_id": f"o{i}"} for i in range(250)
            ]
            + [
                {"task_id": "", "objective_id": "o"},
                {"task_id": "ok", "objective_id": ""},
            ],
            "key_brings": [f"k{i}" for i in range(100)],
        }
    )
    assert len(body.selected) == 40
    assert len(body.objective_dones) == 200
    assert len(body.key_brings) == 80
    assert body.objective_dones[0].task_id == "t0"
