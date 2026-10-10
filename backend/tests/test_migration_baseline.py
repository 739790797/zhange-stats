"""Baseline 0001 drops the obsolete CircleStats tables, never same-named tables of another app."""

from __future__ import annotations

import logging

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.migrate import _alembic_config

_LEGACY_DDL = (
    "CREATE TABLE games (id INTEGER PRIMARY KEY, name VARCHAR(64) NOT NULL, "
    "platform VARCHAR(64) NOT NULL, icon_url VARCHAR(512), created_at DATETIME NOT NULL)",
    "CREATE TABLE match_records (id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, "
    "game_id INTEGER NOT NULL REFERENCES games (id), played_at DATETIME NOT NULL, "
    "result VARCHAR(8) NOT NULL, mode VARCHAR(64), stats JSON, raw_text TEXT, "
    "source VARCHAR(16) NOT NULL, created_at DATETIME NOT NULL)",
    "CREATE TABLE cs2_matches (id INTEGER PRIMARY KEY, match_id VARCHAR(32) NOT NULL UNIQUE, "
    "outcome_id VARCHAR(32), token INTEGER, share_code VARCHAR(64), map_name VARCHAR(64), "
    "played_at DATETIME, score_team0 INTEGER, score_team1 INTEGER, demo_url VARCHAR(512), "
    "enriched BOOLEAN NOT NULL, raw_json TEXT, created_at DATETIME NOT NULL, "
    "updated_at DATETIME NOT NULL)",
    "CREATE TABLE cs2_match_players (id INTEGER PRIMARY KEY, "
    "match_id VARCHAR(32) NOT NULL REFERENCES cs2_matches (match_id), "
    "steam_id VARCHAR(32) NOT NULL, member_id INTEGER, team INTEGER, kills INTEGER, "
    "deaths INTEGER, assists INTEGER, mvps INTEGER, score INTEGER, damage INTEGER, "
    "won BOOLEAN, persona_name VARCHAR(128))",
)


@pytest.fixture
def baseline():
    return ScriptDirectory.from_config(_alembic_config()).get_revision("20260731_0001").module


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    try:
        yield engine
    finally:
        engine.dispose()


def _run(engine, baseline, *ddl: str) -> set[str]:
    with engine.begin() as conn:
        for statement in ddl:
            conn.exec_driver_sql(statement)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            baseline._drop_obsolete_tables()
    return set(sa.inspect(engine).get_table_names())


def test_obsolete_tables_are_dropped(engine, baseline) -> None:
    assert _run(engine, baseline, *_LEGACY_DDL) == set()


def test_same_named_table_of_another_app_is_kept(
    engine, baseline, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="zhange.migrate")
    remaining = _run(
        engine,
        baseline,
        "CREATE TABLE games (id INTEGER PRIMARY KEY, title VARCHAR(64))",
        "INSERT INTO games (title) VALUES ('theirs')",
        *_LEGACY_DDL[2:],
    )

    assert remaining == {"games"}
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT title FROM games").scalar() == "theirs"
    warnings = [r.getMessage() for r in caplog.records if r.name == "zhange.migrate"]
    assert len(warnings) == 1 and "games" in warnings[0]


def test_obsolete_table_still_referenced_by_a_kept_table_is_kept(engine, baseline) -> None:
    remaining = _run(
        engine,
        baseline,
        _LEGACY_DDL[0],
        "CREATE TABLE scores (id INTEGER PRIMARY KEY, game_id INTEGER REFERENCES games (id))",
    )

    assert remaining == {"games", "scores"}
