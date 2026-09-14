"""账号级个人资料：阵营 / 版本 / 等级 / 商人好感；蓝边抬仓库。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.tarkov import TarkovUserHideoutLevel, TarkovUserProfile
from app.models.user import User, UserRole
from app.services.tarkov import hideout_levels as levels_svc
from app.services.tarkov import profile as profile_svc
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
                {
                    "level": 3,
                    "station_requirements": [{"station_id": "gen", "level": 2}],
                },
                {
                    "level": 4,
                    "station_requirements": [{"station_id": "gen", "level": 3}],
                },
            ],
        },
        {
            "id": "gen",
            "slug": "generator",
            "levels": [{"level": 1, "station_requirements": []}],
        },
    ]


def test_empty_profile_defaults() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pvp")
    try:
        row = profile_svc.get_profile(db, user.id)
        assert row == {
            "pmc_faction": "",
            "game_edition": "standard",
            "player_level": 1,
            "trader_levels": {},
            "game_mode": "pvp",
        }
        assert db.query(TarkovUserProfile).count() == 0
    finally:
        reset_game_mode(token)


def test_put_faction_traders_and_level() -> None:
    db = _session()
    user = _user(db, "a")
    token = use_game_mode("pvp")
    try:
        out = profile_svc.update_profile(
            db,
            user,
            {
                "pmc_faction": "USEC",
                "player_level": 42,
                "trader_levels": {"prapor": 3, "btr-driver": 4},
            },
            _stations(),
        )
        assert out["pmc_faction"] == "usec"
        assert out["player_level"] == 42
        assert out["trader_levels"] == {"prapor": 3}
        again = profile_svc.update_profile(
            db, user, {"trader_levels": {"therapist": 2}}, _stations()
        )
        assert again["trader_levels"] == {"prapor": 3, "therapist": 2}
    finally:
        reset_game_mode(token)


def test_eod_raises_stash_to_four() -> None:
    db = _session()
    user = _user(db, "a")
    stations = _stations()
    token = use_game_mode("pvp")
    try:
        rows = {r["station_id"]: r["level"] for r in levels_svc.list_levels(db, user.id, stations)}
        assert rows["stash"] == 1
        profile_svc.update_profile(
            db, user, {"game_edition": "eod"}, stations
        )
        rows = {
            r["station_id"]: r["level"]
            for r in levels_svc.list_levels(db, user.id, stations)
        }
        assert rows["stash"] == 4
        stored = {
            (r.station_id, r.level)
            for r in db.query(TarkovUserHideoutLevel).all()
        }
        assert ("stash", 4) in stored
        still = {
            r["station_id"]: r["level"]
            for r in levels_svc.set_level(db, user, stations, "stash", 3)
        }
        assert still["stash"] == 4
        profile_svc.update_profile(
            db, user, {"game_edition": "standard"}, stations
        )
        kept = {
            r["station_id"]: r["level"]
            for r in levels_svc.list_levels(db, user.id, stations)
        }
        assert kept["stash"] == 4
    finally:
        reset_game_mode(token)


def test_pve_profile_separate() -> None:
    db = _session()
    user = _user(db, "a")
    pvp = use_game_mode("pvp")
    try:
        profile_svc.update_profile(
            db, user, {"pmc_faction": "bear", "game_edition": "eod"}, _stations()
        )
    finally:
        reset_game_mode(pvp)
    pve = use_game_mode("pve")
    try:
        row = profile_svc.get_profile(db, user.id)
        assert row["pmc_faction"] == ""
        assert row["game_edition"] == "standard"
        profile_svc.update_profile(
            db, user, {"pmc_faction": "usec"}, _stations()
        )
    finally:
        reset_game_mode(pve)
    pvp_row = profile_svc.get_profile(db, user.id, game_mode="pvp")
    assert pvp_row["pmc_faction"] == "bear"
    assert pvp_row["game_edition"] == "eod"


def test_invalid_faction_and_edition() -> None:
    db = _session()
    user = _user(db, "a")
    with pytest.raises(profile_svc.TarkovProfileError, match="阵营"):
        profile_svc.update_profile(
            db, user, {"pmc_faction": "scav"}, _stations()
        )
    with pytest.raises(profile_svc.TarkovProfileError, match="版本"):
        profile_svc.update_profile(
            db, user, {"game_edition": "unheard"}, _stations()
        )


def test_profile_openapi_requires_login() -> None:
    from app.main import app

    schema = app.openapi()
    paths = (schema.get("paths") or {}).get("/api/guides/tarkov/profile") or {}
    assert paths.get("get", {}).get("security")
    assert paths.get("put", {}).get("security")
