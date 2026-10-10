"""Alembic runner: SQLite batch rebuilds run FK-off, alembic check ignores backfill defaults, app logging survives."""

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
from app.core import database as dbmod
from app.core.config import get_settings
from app.core.database import _install_sqlite_pragmas, configure_engine
from app.core.migrate import _BACKEND_ROOT, _alembic_config, compare_server_default, run_migrations
from app.models.member import Member
from app.models.play_session import PlaySession

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


def _default_diffs(diffs) -> list[tuple[str, str]]:
    flat = [d for group in diffs for d in (group if isinstance(group, list) else [group])]
    return sorted((d[2], d[3]) for d in flat if d[0] == "modify_default")


def test_compare_hook_ignores_backfill_defaults_but_not_missing_ones() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
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

    def diffs(hook) -> list[tuple[str, str]]:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn, opts={"compare_server_default": hook, "target_metadata": metadata}
            )
            return _default_diffs(compare_metadata(ctx, metadata))

    try:
        assert diffs(True) == [("t", "backfilled"), ("t", "missing")]
        assert diffs(compare_server_default) == [("t", "missing")]
    finally:
        engine.dispose()


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
