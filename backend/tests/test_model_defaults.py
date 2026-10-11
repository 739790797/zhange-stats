"""Timestamp defaults are written by Python (Beijing wall clock); DB defaults only mirror migrations."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

import app.models  # noqa: F401
from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member

# NOT NULL timestamps the services always fill in themselves.
_APP_SET = frozenset(
    {
        "minecraft_perf_rollups.bucket_at",
        "minecraft_perf_samples.sampled_at",
        "minecraft_presence_segments.last_seen_at",
        "minecraft_presence_segments.started_at",
        "oauth_exchange_tickets.expires_at",
        "play_sessions.last_seen_at",
        "play_sessions.started_at",
        "presence_segments.last_seen_at",
        "presence_segments.started_at",
        "register_challenges.expires_at",
        "rum_samples.recorded_at",
        "user_files.created_at",
    }
)


def _datetime_columns() -> dict[str, sa.Column]:
    return {
        f"{table.name}.{column.name}": column
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, DateTime)
    }


def test_not_null_timestamps_have_a_python_default() -> None:
    columns = _datetime_columns()
    missing = sorted(
        name
        for name, col in columns.items()
        if not col.nullable and col.default is None and name not in _APP_SET
    )
    assert missing == []
    assert _APP_SET <= set(columns)
    stale = sorted(name for name in _APP_SET if columns[name].default is not None)
    assert stale == []


def test_timestamp_defaults_are_never_sql_expressions() -> None:
    bad: list[str] = []
    for name, col in _datetime_columns().items():
        for kind, value in (("default", col.default), ("onupdate", col.onupdate)):
            if value is not None and getattr(value, "is_clause_element", False):
                bad.append(f"{name}: SQL {kind}")
        if col.server_onupdate is not None:
            bad.append(f"{name}: server_onupdate")
        if col.server_default is None:
            continue
        arg = col.server_default.arg
        if not (isinstance(arg, TextClause) and arg.text == "CURRENT_TIMESTAMP"):
            bad.append(f"{name}: server_default {arg!r}")
        if col.default is None:
            bad.append(f"{name}: server_default without a Python default")
    assert bad == []


def test_python_defaults_write_beijing_wall_clock() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            before = now_naive()
            member = Member(nickname="m")
            db.add(member)
            db.commit()
            assert before <= member.joined_at <= now_naive()

            stale = datetime(2020, 1, 1)
            pref = CheckinRolePref(
                platform="skland",
                member_id=member.id,
                game_code="arknights",
                role_uid="1",
                updated_at=stale,
            )
            db.add(pref)
            db.commit()
            assert pref.updated_at == stale

            before = now_naive()
            pref.enabled = True
            db.commit()
            assert before <= pref.updated_at <= now_naive()
    finally:
        engine.dispose()
