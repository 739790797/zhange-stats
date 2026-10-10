"""MariaDB migration checks. Skipped unless ZHANGE_TEST_MYSQL_URL names a scratch database.

Every test drops all tables in that database first.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core import database as dbmod
from app.core.beijing_time_migrate import ensure_beijing_time_storage
from app.core.config import get_settings
from app.core.database import Base, configure_engine
from app.core.migrate import _alembic_config, compare_server_default, run_migrations
from app.models.minecraft import MinecraftServerProfile
from app.models.system_config import SystemConfig

MYSQL_URL = (os.environ.get("ZHANGE_TEST_MYSQL_URL") or "").strip()

pytestmark = pytest.mark.skipif(not MYSQL_URL, reason="ZHANGE_TEST_MYSQL_URL not set")

_UTC_STARTED = datetime(2026, 7, 31, 16, 0)


def _wipe(engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 0")
        for name in sa.inspect(conn).get_table_names():
            conn.exec_driver_sql(f"DROP TABLE `{name}`")
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")


@pytest.fixture
def mariadb(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", MYSQL_URL)
    get_settings.cache_clear()
    engine = configure_engine()
    _wipe(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        dbmod._engine = None
        dbmod._SessionLocal = None
        get_settings.cache_clear()


def _schema_diffs(engine) -> list:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn,
            opts={
                "compare_type": True,
                "compare_server_default": compare_server_default,
                "target_metadata": Base.metadata,
            },
        )
        return compare_metadata(ctx, Base.metadata)


def _marker(engine) -> str | None:
    with Session(engine) as db:
        row = db.get(SystemConfig, "time_storage")
        return row.value if row is not None else None


def _seed_utc_job_run(engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO job_runs (job_key, started_at, status) VALUES ('probe', %s, 'ok')",
            (_UTC_STARTED,),
        )


def _job_started(engine) -> datetime:
    with engine.connect() as conn:
        return conn.exec_driver_sql(
            "SELECT started_at FROM job_runs WHERE job_key = 'probe'"
        ).scalar_one()


def _ensure_twice(engine) -> None:
    for _ in range(2):
        with Session(engine) as db:
            ensure_beijing_time_storage(db, engine)


def test_fresh_chain_runs_twice_and_matches_models(mariadb) -> None:
    run_migrations()
    run_migrations()

    assert _schema_diffs(mariadb) == []
    assert _marker(mariadb) == "beijing_v1"


def test_utc_era_database_is_shifted_once(mariadb) -> None:
    command.upgrade(_alembic_config(), "20260801_0006")
    _seed_utc_job_run(mariadb)

    run_migrations()
    assert _marker(mariadb) == "utc_pending"

    _ensure_twice(mariadb)
    assert _job_started(mariadb) == datetime(2026, 8, 1, 0, 0)
    assert _marker(mariadb) == "beijing_v1"


def test_unmarked_database_built_after_the_switch_is_not_shifted(mariadb) -> None:
    run_migrations()
    with mariadb.begin() as conn:
        conn.exec_driver_sql("DELETE FROM system_configs WHERE `key` = 'time_storage'")
    _seed_utc_job_run(mariadb)

    _ensure_twice(mariadb)
    assert _job_started(mariadb) == _UTC_STARTED
    assert _marker(mariadb) == "beijing_v1"


def test_0119_repairs_legacy_shapes_back_to_the_models(mariadb) -> None:
    run_migrations()
    with Session(mariadb) as db:
        db.add(MinecraftServerProfile(id=1))
        db.add(SystemConfig(key="integrations", value=json.dumps({"github_token": "t"})))
        db.commit()
    with mariadb.begin() as conn:
        conn.exec_driver_sql("DROP TABLE register_challenges")
        conn.exec_driver_sql(
            "CREATE TABLE register_challenges (email VARCHAR(128) NOT NULL PRIMARY KEY, "
            "code VARCHAR(16) NOT NULL, expires_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO register_challenges VALUES ('a@example.com', '123456', NOW())"
        )
        conn.exec_driver_sql(
            "ALTER TABLE minecraft_server_profiles "
            "ADD COLUMN public_host VARCHAR(255) NULL, ADD COLUMN public_port INT NULL"
        )
        conn.exec_driver_sql(
            "UPDATE minecraft_server_profiles "
            "SET public_host = 'mc.example.com', public_port = 25566 WHERE id = 1"
        )
        conn.exec_driver_sql("DROP INDEX ix_arknights_operators_rarity ON arknights_operators")

    cfg = _alembic_config()
    command.stamp(cfg, "20261010_0118")
    command.upgrade(cfg, "head")

    assert _schema_diffs(mariadb) == []
    with mariadb.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT email, purpose, code, attempts FROM register_challenges"
        ).fetchall()
    assert [tuple(r) for r in rows] == [("a@example.com", "register", "123456", 0)]
    with Session(mariadb) as db:
        stored = json.loads(db.get(SystemConfig, "integrations").value)
    assert stored["minecraft_public_host"] == "mc.example.com"
    assert stored["minecraft_public_port"] == 25566
