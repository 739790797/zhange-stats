"""box_role_cache：从 raw 表还原角色列表。"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models.arknights_rogue import ArknightsRogueRaw
from app.models.endfield import EndfieldBoxRaw
from app.models.exastris import ExastrisBoxRaw
from app.models.kujiequ import KujiequWwBoxRaw
from app.models.member import Member
from app.models.skland import SklandAttendanceRaw, SklandBind, SklandCheckinLog
from app.services.box_role_cache import (
    kujiequ_ww_roles_from_raws,
    skland_arknights_roles_from_raws,
    skland_endfield_roles_from_raws,
    taygedo_nte_roles_from_raws,
)
from app.services.kujiequ.client import GAME_WW
from app.services.skland.client import GAME_ARKNIGHTS, GAME_ENDFIELD
from app.services.taygedo.client import GAME_NTE


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine, autoflush=False)()
    for member_id in (1, 2):
        session.add(Member(id=member_id, nickname=f"m{member_id}"))
        session.add(SklandBind(id=member_id, member_id=member_id, token_enc="x"))
    session.commit()
    yield session
    session.close()


def _log(
    day: date, uid: str, role_name: str, channel_name: str, *, member_id: int = 1
) -> SklandCheckinLog:
    return SklandCheckinLog(
        member_id=member_id,
        bind_id=member_id,
        game_code=GAME_ARKNIGHTS,
        game_name="明日方舟",
        role_uid=uid,
        role_name=role_name,
        channel_name=channel_name,
        status="ok",
        checkin_date=day,
        checked_at=datetime(day.year, day.month, day.day, 8),
    )


def test_skland_endfield_roles_from_raws(db) -> None:
    db.add(EndfieldBoxRaw(member_id=1, role_id="r1", server_id="s1", uid="u1", raw_json="{}"))
    db.commit()
    roles = skland_endfield_roles_from_raws(db, 1)
    assert roles is not None
    assert len(roles) == 1
    assert roles[0].game_code == GAME_ENDFIELD
    assert (roles[0].role_id, roles[0].uid, roles[0].server_id) == ("r1", "u1", "s1")


def test_skland_arknights_roles_from_rogue_raws_use_checkin_logs(db) -> None:
    db.add_all(
        [
            ArknightsRogueRaw(member_id=1, uid="289253581", topic_id="rogue_4", raw_json="{}"),
            ArknightsRogueRaw(member_id=1, uid="289253581", topic_id="rogue_5", raw_json="{}"),
            _log(date(2026, 9, 9), "289253581", "白衣#5820", "bilibili服"),
        ]
    )
    db.commit()
    roles = skland_arknights_roles_from_raws(db, 1)
    assert roles is not None
    assert len(roles) == 1
    assert roles[0].game_code == GAME_ARKNIGHTS
    assert roles[0].uid == "289253581"
    assert roles[0].role_name == "白衣#5820"
    assert roles[0].channel_name == "B服"


def test_skland_arknights_roles_from_attendance_keep_names(db) -> None:
    db.add(
        SklandAttendanceRaw(
            member_id=1, uid="1", role_name="白衣#5820", channel_name="官服", raw_json="{}"
        )
    )
    db.commit()
    roles = skland_arknights_roles_from_raws(db, 1)
    assert roles is not None
    assert roles[0].role_name == "白衣#5820"
    assert roles[0].channel_name == "官服"


def test_skland_arknights_roles_none_without_raws(db) -> None:
    db.add(_log(date(2026, 9, 9), "1", "白衣#5820", "官服"))
    db.commit()
    assert skland_arknights_roles_from_raws(db, 1) is None


def test_skland_arknights_rogue_role_is_labelled_from_its_latest_log_day(db) -> None:
    db.add_all(
        [
            ArknightsRogueRaw(member_id=1, uid="7", topic_id="rogue_4", raw_json="{}"),
            _log(date(2026, 9, 8), "7", "旧名#1", "bilibili服"),
            _log(date(2026, 9, 10), "7", "新名#1", "官服"),
            _log(date(2026, 9, 9), "7", "中间#1", "bilibili服"),
            _log(date(2026, 9, 10), "7", "别人#2", "bilibili服", member_id=2),
            _log(date(2026, 9, 11), "7", "别人#2", "bilibili服", member_id=2),
        ]
    )
    db.commit()
    roles = skland_arknights_roles_from_raws(db, 1)
    assert roles is not None
    assert [(r.uid, r.role_name, r.channel_name) for r in roles] == [("7", "新名#1", "官服")]


def test_attendance_role_missing_channel_takes_it_from_logs(db) -> None:
    db.add_all(
        [
            SklandAttendanceRaw(
                member_id=1, uid="1", role_name="白衣#5820", channel_name=None, raw_json="{}"
            ),
            ArknightsRogueRaw(member_id=1, uid="1", topic_id="rogue_4", raw_json="{}"),
            _log(date(2026, 9, 9), "1", "旧名#5820", "bilibili服"),
        ]
    )
    db.commit()
    roles = skland_arknights_roles_from_raws(db, 1)
    assert roles is not None
    assert [(r.uid, r.role_name, r.channel_name) for r in roles] == [("1", "白衣#5820", "B服")]


def test_role_lists_never_load_raw_json(engine, db) -> None:
    db.add_all(
        [
            SklandAttendanceRaw(member_id=1, uid="1", raw_json="{}"),
            ArknightsRogueRaw(member_id=1, uid="2", topic_id="rogue_4", raw_json="{}"),
            _log(date(2026, 9, 9), "2", "白衣#5820", "官服"),
            EndfieldBoxRaw(member_id=1, role_id="r1", raw_json="{}"),
            ExastrisBoxRaw(member_id=1, role_id="n1", raw_json="{}"),
            KujiequWwBoxRaw(member_id=1, role_id="w1", raw_json="{}"),
        ]
    )
    db.commit()
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        arknights = skland_arknights_roles_from_raws(db, 1)
        endfield = skland_endfield_roles_from_raws(db, 1)
        nte = taygedo_nte_roles_from_raws(db, 1)
        ww = kujiequ_ww_roles_from_raws(db, 1)
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert arknights is not None and [r.uid for r in arknights] == ["1", "2"]
    assert endfield is not None and [r.role_id for r in endfield] == ["r1"]
    assert nte is not None and [(r.game_code, r.role_id) for r in nte] == [(GAME_NTE, "n1")]
    assert ww is not None and [(r.game_id, r.role_id) for r in ww] == [(GAME_WW, "w1")]
    assert statements
    assert not [s for s in statements if "raw_json" in s]
    assert skland_endfield_roles_from_raws(db, 2) is None
    assert taygedo_nte_roles_from_raws(db, 2) is None
    assert kujiequ_ww_roles_from_raws(db, 2) is None
