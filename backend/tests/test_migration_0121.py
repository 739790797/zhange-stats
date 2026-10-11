"""Migration 0121: DB defaults of the opt-in flags agree with the models (0); stored values stay."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base
from app.core.migrate import _alembic_config

_REVISION = "20261010_0121"
_INSERT_PREF = (
    "INSERT INTO checkin_role_prefs (platform, member_id, game_code, role_uid, enabled) "
    "VALUES ('skland', 1, 'arknights', ?, 0)"
)


@pytest.fixture
def plain_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{tmp_path / 'zhange.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


def _upgrade() -> None:
    cfg = _alembic_config()
    parent = ScriptDirectory.from_config(cfg).get_revision(_REVISION).down_revision
    command.stamp(cfg, parent)
    command.upgrade(cfg, _REVISION)


def _default(engine, table: str, column: str) -> str | None:
    return {c["name"]: c for c in sa.inspect(engine).get_columns(table)}[column]["default"]


def _table_sql(engine, table: str) -> str:
    with engine.connect() as conn:
        return conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).scalar_one()


def _included(engine) -> dict[str, int]:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT role_uid, included FROM checkin_role_prefs")
        return {uid: included for uid, included in rows}


def test_default_of_one_becomes_zero_and_stored_values_stay(plain_engine) -> None:
    # The MariaDB shape 0029 left behind: DEFAULT 1, and a row that relied on it.
    with plain_engine.begin() as conn:
        with Operations(MigrationContext.configure(conn)).batch_alter_table(
            "checkin_role_prefs"
        ) as batch:
            batch.alter_column(
                "included",
                existing_type=sa.Boolean(),
                existing_nullable=False,
                server_default=sa.text("1"),
            )
        conn.exec_driver_sql("INSERT INTO members (id, nickname) VALUES (1, 'm')")
        conn.exec_driver_sql(_INSERT_PREF, ("old",))
    assert _included(plain_engine) == {"old": 1}
    without_default = _table_sql(plain_engine, "skland_binds")

    _upgrade()

    assert _default(plain_engine, "checkin_role_prefs", "included") == "0"
    with plain_engine.begin() as conn:
        conn.exec_driver_sql(_INSERT_PREF, ("new",))
    assert _included(plain_engine) == {"old": 1, "new": 0}
    # create_all gave auto_checkin no DB default: left alone, no rebuild
    assert _table_sql(plain_engine, "skland_binds") == without_default

    _upgrade()
    assert _default(plain_engine, "checkin_role_prefs", "included") == "0"
    assert _included(plain_engine) == {"old": 1, "new": 0}
