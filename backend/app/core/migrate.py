"""Run Alembic migrations against the configured database."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.beijing_time_migrate import (
    UTC_ERA_REVISIONS,
    current_revision,
    record_time_storage_origin,
)
from app.core.database import Base, get_engine
from app.core.schema_ensure import ensure_schema

logger = logging.getLogger("zhange.migrate")

_REQUIRED_TABLES = (
    "users",
    "members",
    "register_challenges",
    "job_runs",
    "system_configs",
    "play_sessions",
    "presence_segments",
    "steam_apps",
    "skland_binds",
    "taygedo_binds",
    "exilium_binds",
    "kujiequ_binds",
    "mihoyo_binds",
    "checkin_role_prefs",
    "oauth_exchange_tickets",
)

_REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "users": frozenset({"email", "role", "email_verified"}),
    "members": frozenset(
        {
            "steam_id",
            "steam_persona_name",
            "user_id",
        }
    ),
    "skland_binds": frozenset({"member_id", "cred_enc", "auto_checkin"}),
    "checkin_role_prefs": frozenset(
        {
            "member_id",
            "platform",
            "game_code",
            "role_uid",
            "included",
            "enabled",
        }
    ),
}

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    # Read alembic.ini as UTF-8; Windows locale (GBK) breaks non-ASCII comments.
    from configparser import ConfigParser

    ini = _BACKEND_ROOT / "alembic.ini"
    parser = ConfigParser()
    parser.read(str(ini), encoding="utf-8")
    cfg = Config()
    cfg.config_file_name = str(ini)
    cfg.__dict__["file_config"] = parser
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    # env.py would otherwise fileConfig() alembic.ini and drop the app's log handlers.
    cfg.attributes["configure_logger"] = False
    return cfg


def compare_server_default(
    context,
    inspected_column,
    metadata_column,
    inspected_default,
    metadata_default,
    rendered_metadata_default,
):
    """Alembic autogenerate hook (alembic/env.py).

    Migrations give NOT NULL columns a DB default only to backfill existing rows. When the
    model has a Python-side default the ORM always writes the value, so a DB-only default is
    not drift. A model server_default the DB lacks is still reported.
    """
    if metadata_default is None and metadata_column.default is not None:
        return False
    return None


def _verify_aligned_schema() -> None:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())
    missing_tables = [t for t in _REQUIRED_TABLES if t not in tables]
    if missing_tables:
        raise RuntimeError(
            "Legacy schema alignment incomplete; missing tables: "
            + ", ".join(missing_tables)
        )
    for table, required in _REQUIRED_COLUMNS.items():
        columns = {c["name"] for c in inspector.get_columns(table)}
        missing = sorted(required - columns)
        if missing:
            raise RuntimeError(
                f"Legacy schema alignment incomplete; {table} missing columns: "
                + ", ".join(missing)
            )


def _align_legacy_schema() -> None:
    """Bring pre-Alembic databases up to current models before stamping."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    ensure_schema(get_engine())
    _verify_aligned_schema()


def _run_sqlite_schema(engine: Engine) -> None:
    import app.models  # noqa: F401

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    cfg = _alembic_config()
    if "alembic_version" in tables:
        command.upgrade(cfg, "head")
    else:
        Base.metadata.create_all(bind=engine)
        command.stamp(cfg, "head")
    record_time_storage_origin(engine, utc_era=False)
    logger.info("SQLite schema is up to date")


def _run_server_schema(engine: Engine) -> None:
    cfg = _alembic_config()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    try:
        if "alembic_version" not in tables and "users" in tables:
            logger.warning(
                "Legacy schema path: ensure_schema + stamp head. "
                "New schema changes must use Alembic only; do not extend schema_ensure."
            )
            logger.info(
                "Existing schema detected without alembic_version; "
                "aligning schema then stamping baseline as applied"
            )
            _align_legacy_schema()
            # Pre-Alembic data predates the Beijing wall-clock switch.
            record_time_storage_origin(engine, utc_era=True)
            command.stamp(cfg, "head")
        elif "alembic_version" not in tables:
            leftover = sorted(set(_REQUIRED_TABLES) & tables)
            if leftover:
                raise RuntimeError(
                    "Incomplete database without users/alembic_version; "
                    f"leftover tables: {', '.join(leftover)}. "
                    "Restore a backup or drop these tables before starting."
                )
            command.upgrade(cfg, "head")
        else:
            # Classify before upgrading: afterwards the revision no longer tells UTC-era data apart.
            record_time_storage_origin(
                engine, utc_era=current_revision(engine) in UTC_ERA_REVISIONS
            )
            command.upgrade(cfg, "head")
    except Exception as exc:
        msg = str(exc)
        logger.exception("Database migration failed: %s", msg)
        if "present more than once" in msg or "overlaps with other requested revisions" in msg:
            raise RuntimeError(
                "Alembic 修订号冲突（常见于 v0.2.37 双 0056）。"
                "请在主机拉代码后执行 scripts/linux/install.sh 与 scripts/linux/restart.sh"
            ) from exc
        if (
            "Duplicate column" in msg
            or "1060" in msg
            or "already exists" in msg.lower()
        ):
            raise RuntimeError(
                "迁移半完成（对象已存在但 alembic_version 未前进；常见于 MySQL/MariaDB "
                "非事务 DDL）。请确认迁移幂等后重试，或在主机拉代码后执行 "
                "scripts/linux/install.sh 与 scripts/linux/restart.sh"
            ) from exc
        raise

    # Schema built from an empty database: everything it holds is Beijing wall clock.
    record_time_storage_origin(engine, utc_era=False)
    logger.info("Database migrations are up to date")


def run_migrations() -> None:
    """Apply pending migrations; stamp existing create_all databases once."""
    engine = get_engine()
    before = current_revision(engine)
    if engine.dialect.name == "sqlite":
        _run_sqlite_schema(engine)
    else:
        _run_server_schema(engine)
    after = current_revision(engine)
    if after != before:
        logger.info("database schema revision %s -> %s", before or "(none)", after)
