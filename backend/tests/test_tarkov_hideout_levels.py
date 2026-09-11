"""账号级藏身处等级：按 PVP/PVE 分开，缺行仓库为 1。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.tarkov import TarkovUserHideoutLevel
from app.models.user import User, UserRole
from app.services.tarkov import hideout_levels as levels_svc
from app.services.tarkov.game_mode import reset_game_mode, use_game_mode


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


def _stations() -> list[dict]:
    return [
        {
            "id": "stash",
            "slug": "stash",
            "levels": [
                {"level": 1, "station_requirements": []},
                {
                    "level": 2,
                    "station_requirements": [{"station_id": "gen", "level": 1}],
                },
            ],
        },
        {
            "id": "gen",
            "slug": "generator",
            "levels": [
                {"level": 1, "station_requirements": []},
                {
                    "level": 2,
                    "station_requirements": [{"station_id": "stash", "level": 2}],
                },
            ],
        },
        {
            "id": "bench",
            "slug": "workbench",
            "levels": [
                {
                    "level": 1,
                    "station_requirements": [{"station_id": "gen", "level": 1}],
                }
            ],
        },
    ]


def test_list_defaults_and_set_persists_nonzero() -> None:
    db = _session()
    user = _user(db, "a")
    stations = _stations()
    token = use_game_mode("pvp")
    try:
        rows = {r["station_id"]: r["level"] for r in levels_svc.list_levels(db, user.id, stations)}
        assert rows == {"bench": 0, "gen": 0, "stash": 1}
        out = levels_svc.set_level(db, user, stations, "gen", 1)
        by_id = {r["station_id"]: r["level"] for r in out}
        assert by_id["gen"] == 1
        stored = db.query(TarkovUserHideoutLevel).all()
        assert {(r.station_id, r.level) for r in stored} == {("gen", 1)}
        levels_svc.set_level(db, user, stations, "gen", 0)
        assert db.query(TarkovUserHideoutLevel).count() == 0
    finally:
        reset_game_mode(token)


def test_pve_separate_and_cascade() -> None:
    db = _session()
    user = _user(db, "a")
    stations = _stations()
    pvp = use_game_mode("pvp")
    try:
        levels_svc.set_level(db, user, stations, "gen", 1)
        levels_svc.set_level(db, user, stations, "bench", 1)
        levels_svc.set_level(db, user, stations, "stash", 2)
        levels_svc.set_level(db, user, stations, "gen", 2)
    finally:
        reset_game_mode(pvp)
    pve = use_game_mode("pve")
    try:
        rows = {r["station_id"]: r["level"] for r in levels_svc.list_levels(db, user.id, stations)}
        assert rows["gen"] == 0
        levels_svc.set_level(db, user, stations, "gen", 1)
    finally:
        reset_game_mode(pve)
    pvp_rows = {
        r["station_id"]: r["level"]
        for r in levels_svc.list_levels(db, user.id, stations, game_mode="pvp")
    }
    assert pvp_rows["gen"] == 2
    assert pvp_rows["bench"] == 1
    mid = {
        r["station_id"]: r["level"]
        for r in levels_svc.set_level(db, user, stations, "gen", 1, game_mode="pvp")
    }
    assert mid["gen"] == 1
    dropped = {
        r["station_id"]: r["level"]
        for r in levels_svc.set_level(db, user, stations, "gen", 0, game_mode="pvp")
    }
    assert dropped["bench"] == 0
    assert dropped["stash"] == 1


def test_unknown_station_rejected() -> None:
    db = _session()
    user = _user(db, "a")
    with pytest.raises(levels_svc.TarkovHideoutLevelsError):
        levels_svc.set_level(db, user, _stations(), "nope", 1)


def test_hideout_levels_openapi_requires_login() -> None:
    from app.main import app

    schema = app.openapi()
    paths = (schema.get("paths") or {}).get("/api/guides/tarkov/hideout-levels") or {}
    assert paths.get("get", {}).get("security")
    assert paths.get("put", {}).get("security")
