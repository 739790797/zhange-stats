"""Alembic runner: SQLite batch rebuilds run FK-off, env.py marks UTC-era upgrades, alembic check
ignores backfill defaults unless they contradict the model, app logging survives."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core import beijing_time_migrate as btm
from app.core import database as dbmod
from app.core.config import get_settings
from app.core.database import _install_sqlite_pragmas, configure_engine
from app.core.migrate import _BACKEND_ROOT, _alembic_config, compare_server_default, run_migrations
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.system_config import SystemConfig
from app.models.user import UserRole

_NOW = datetime(2026, 10, 10, 12, 0)

_PROBE_REVISION = '''
import sqlalchemy as sa
from alembic import op

revision = "zz_fk_probe"
down_revision = "{down}"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("members", recreate="always") as batch:
        batch.add_column(sa.Column("fk_probe", sa.Integer(), nullable=True))


def downgrade():
    pass
'''

_NOOP_REVISION = '''
revision = "zz_noop_probe"
down_revision = "{down}"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
'''


@pytest.fixture
def sqlite_app_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'zhange.sqlite'}")
    get_settings.cache_clear()
    engine = configure_engine()
    try:
        yield engine
    finally:
        engine.dispose()
        dbmod._engine = None
        dbmod._SessionLocal = None
        get_settings.cache_clear()


def _count_sessions(conn, member_id: int) -> int:
    table = PlaySession.__table__
    return conn.execute(
        select(func.count()).select_from(table).where(table.c.member_id == member_id)
    ).scalar_one()


@pytest.mark.parametrize("migration_fks", ["off", "on"])
def test_batch_rebuild_keeps_child_rows_only_with_foreign_keys_off(
    sqlite_app_db,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    migration_fks: str,
) -> None:
    run_migrations()
    with Session(sqlite_app_db) as db:
        member = Member(nickname="m1")
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
        db.commit()
        member_id = member.id

    if migration_fks == "on":
        # What env.py would do if it reused the app engine's pragmas.
        monkeypatch.setattr(
            dbmod,
            "prepare_migration_engine",
            lambda engine: _install_sqlite_pragmas(engine, file_db=True),
        )

    cfg = _alembic_config()
    head = ScriptDirectory.from_config(cfg).get_current_head()
    probe_dir = tmp_path / "probe_versions"
    probe_dir.mkdir()
    (probe_dir / "zz_fk_probe.py").write_text(
        _PROBE_REVISION.format(down=head), encoding="utf-8"
    )
    cfg.set_main_option(
        "version_locations",
        os.pathsep.join([str(_BACKEND_ROOT / "alembic" / "versions"), str(probe_dir)]),
    )
    command.upgrade(cfg, "zz_fk_probe")

    with sqlite_app_db.connect() as conn:
        assert "fk_probe" in {c["name"] for c in sa.inspect(conn).get_columns("members")}
        if migration_fks == "off":
            assert _count_sessions(conn, member_id) == 1
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        else:
            assert _count_sessions(conn, member_id) == 0


@pytest.mark.parametrize(
    ("utc_era_head", "expected"), [(True, "utc_pending"), (False, None)]
)
def test_cli_upgrade_marks_utc_era_databases_through_env_py(
    sqlite_app_db,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    utc_era_head: bool,
    expected: str | None,
) -> None:
    run_migrations()
    with sqlite_app_db.begin() as conn:
        conn.exec_driver_sql("""DELETE FROM system_configs WHERE "key" = 'time_storage'""")
    cfg = _alembic_config()
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if utc_era_head:
        # Pretend the current head is still a UTC-era revision.
        monkeypatch.setattr(btm, "UTC_ERA_REVISIONS", frozenset({head}))
    probe_dir = tmp_path / "noop_versions"
    probe_dir.mkdir()
    (probe_dir / "zz_noop_probe.py").write_text(_NOOP_REVISION.format(down=head), encoding="utf-8")
    cfg.set_main_option(
        "version_locations",
        os.pathsep.join([str(_BACKEND_ROOT / "alembic" / "versions"), str(probe_dir)]),
    )

    # What `alembic upgrade` on the command line runs: env.py, without run_migrations().
    command.upgrade(cfg, "zz_noop_probe")

    with Session(sqlite_app_db) as db:
        row = db.get(SystemConfig, "time_storage")
        assert (row.value if row is not None else None) == expected


def _default_diffs(diffs) -> list[tuple[str, str]]:
    flat = [d for group in diffs for d in (group if isinstance(group, list) else [group])]
    return sorted((d[2], d[3]) for d in flat if d[0] == "modify_default")


def _hook_diffs(ddl: str, metadata: sa.MetaData, hook) -> list[tuple[str, str]]:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(ddl)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn, opts={"compare_server_default": hook, "target_metadata": metadata}
            )
            return _default_diffs(compare_metadata(ctx, metadata))
    finally:
        engine.dispose()


def test_compare_hook_ignores_backfill_defaults_but_not_missing_ones() -> None:
    ddl = (
        "CREATE TABLE t (id INTEGER NOT NULL PRIMARY KEY, "
        "backfilled INTEGER NOT NULL DEFAULT 0, missing INTEGER NOT NULL)"
    )
    metadata = sa.MetaData()
    sa.Table(
        "t",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("backfilled", sa.Integer, nullable=False, default=0),
        sa.Column("missing", sa.Integer, nullable=False, server_default="1"),
    )

    assert _hook_diffs(ddl, metadata, True) == [("t", "backfilled"), ("t", "missing")]
    assert _hook_diffs(ddl, metadata, compare_server_default) == [("t", "missing")]


def test_compare_hook_reports_backfill_defaults_that_contradict_the_model() -> None:
    ddl = (
        "CREATE TABLE t (id INTEGER NOT NULL PRIMARY KEY, "
        "opted_in BOOLEAN NOT NULL DEFAULT 1, "
        "opted_out BOOLEAN NOT NULL DEFAULT '0', "
        "role VARCHAR(5) NOT NULL DEFAULT 'user', "
        "hour INTEGER NOT NULL DEFAULT (5), "
        "label VARCHAR(8) NOT NULL DEFAULT 'b', "
        "stamped DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    metadata = sa.MetaData()
    sa.Table(
        "t",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("opted_in", sa.Boolean, nullable=False, default=False),
        sa.Column("opted_out", sa.Boolean, nullable=False, default=False),
        sa.Column(
            "role",
            sa.Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
            nullable=False,
            default=UserRole.user,
        ),
        sa.Column("hour", sa.Integer, nullable=False, default=5),
        sa.Column("label", sa.String(8), nullable=False, default="a"),
        sa.Column("stamped", sa.DateTime, nullable=False, default=lambda: _NOW),
    )

    assert _hook_diffs(ddl, metadata, compare_server_default) == [
        ("t", "label"),
        ("t", "opted_in"),
    ]


def test_run_migrations_keeps_app_loggers_and_root_handlers(sqlite_app_db) -> None:
    probe = logging.getLogger("zhange.migrate_probe")
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level

    run_migrations()

    assert probe.disabled is False
    assert logging.getLogger("zhange.startup").disabled is False
    assert root.handlers == handlers
    assert root.level == level


def test_revision_change_is_logged_once(
    sqlite_app_db, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="zhange.migrate")
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()

    run_migrations()
    run_migrations()

    changes = [r.getMessage() for r in caplog.records if "schema revision" in r.getMessage()]
    assert changes == [f"database schema revision (none) -> {head}"]
