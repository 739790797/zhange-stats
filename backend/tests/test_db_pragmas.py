"""SQLite pragmas: the app engine enforces foreign keys; Alembic's engine keeps them off."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.biz_logging import clear_log_until_change
from app.core.database import (
    SQLITE_BUSY_TIMEOUT_MS,
    Base,
    _build_engine,
    _sqlite_is_file,
    prepare_migration_engine,
)
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.tarkov import TarkovRaidRoom
from app.models.user import User

_NOW = datetime(2026, 10, 10, 12, 0)


def _pragmas(conn) -> dict[str, object]:
    return {
        name: conn.exec_driver_sql(f"PRAGMA {name}").scalar()
        for name in ("foreign_keys", "journal_mode", "synchronous", "busy_timeout")
    }


def _count_sessions(conn, member_id: int) -> int:
    table = PlaySession.__table__
    return conn.execute(
        select(func.count()).select_from(table).where(table.c.member_id == member_id)
    ).scalar_one()


def test_file_engine_enables_foreign_keys_and_wal_on_every_connection(tmp_path: Path) -> None:
    engine = _build_engine(f"sqlite:///{tmp_path / 'zhange.sqlite'}")
    try:
        with engine.connect() as first, engine.connect() as second:
            for conn in (first, second):
                assert _pragmas(conn) == {
                    "foreign_keys": 1,
                    "journal_mode": "wal",
                    "synchronous": 1,
                    "busy_timeout": SQLITE_BUSY_TIMEOUT_MS,
                }
    finally:
        engine.dispose()


def test_memory_engine_enables_foreign_keys_without_wal() -> None:
    engine = _build_engine("sqlite:///:memory:")
    try:
        with engine.connect() as conn:
            assert _pragmas(conn) == {
                "foreign_keys": 1,
                "journal_mode": "memory",
                "synchronous": 2,
                "busy_timeout": SQLITE_BUSY_TIMEOUT_MS,
            }
    finally:
        engine.dispose()


def test_read_only_file_keeps_rollback_journal_and_warns_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "readonly.sqlite"
    sqlite3.connect(path).close()
    clear_log_until_change()
    caplog.set_level(logging.DEBUG, logger="zhange.db")
    engine = _build_engine(f"sqlite:///file:{path}?mode=ro&uri=true")
    try:
        with engine.connect() as first, engine.connect() as second:
            for conn in (first, second):
                pragmas = _pragmas(conn)
                assert pragmas["foreign_keys"] == 1
                assert pragmas["journal_mode"] != "wal"
                assert pragmas["synchronous"] == 2
    finally:
        engine.dispose()
        clear_log_until_change()
    warnings = [
        r for r in caplog.records if r.name == "zhange.db" and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert "WAL unavailable" in warnings[0].getMessage()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:///:memory:", False),
        ("sqlite://", False),
        ("sqlite:///file::memory:?cache=shared&uri=true", False),
        ("sqlite:///file:shared?mode=memory&cache=shared&uri=true", False),
        ("sqlite:////srv/zhange/data/runtime/zhange.sqlite", True),
        ("sqlite:///relative.sqlite", True),
    ],
)
def test_sqlite_is_file(url: str, expected: bool) -> None:
    assert _sqlite_is_file(url) is expected


def test_migration_engine_turns_foreign_keys_off(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'm.sqlite'}", poolclass=sa.pool.NullPool)
    prepare_migration_engine(engine)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 0
        assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == SQLITE_BUSY_TIMEOUT_MS


def test_deletes_cascade_and_a_reused_member_id_starts_clean(tmp_path: Path) -> None:
    engine = _build_engine(f"sqlite:///{tmp_path / 'zhange.sqlite'}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(username="u1", display_name="U1", password_hash="x")
            db.add(user)
            db.flush()
            member = Member(nickname="m1", user_id=user.id)
            db.add(member)
            db.flush()
            db.add(
                PlaySession(
                    member_id=member.id,
                    steam_app_id="730",
                    game_name="CS2",
                    started_at=_NOW,
                    last_seen_at=_NOW,
                )
            )
            db.add(TarkovRaidRoom(public_id="R1", host_user_id=user.id))
            db.commit()
            old_member_id = member.id

        # Core DELETE: only the database's ON DELETE actions run, no ORM cascade.
        with engine.begin() as conn:
            conn.execute(sa.delete(User.__table__))

        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Member)) == 0
            assert db.scalar(select(func.count()).select_from(PlaySession)) == 0
            assert db.scalar(select(TarkovRaidRoom.host_user_id)) is None

            newcomer = Member(nickname="m2")
            db.add(newcomer)
            db.commit()
            # members.id has no AUTOINCREMENT on SQLite, so the freed id is handed out again.
            assert newcomer.id == old_member_id
            assert _count_sessions(db.connection(), newcomer.id) == 0
    finally:
        engine.dispose()
