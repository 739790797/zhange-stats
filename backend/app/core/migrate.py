"""Run Alembic migrations against the configured database."""

from __future__ import annotations

import enum
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.beijing_time_migrate import current_revision, record_time_storage_origin
from app.core.database import Base, get_engine

logger = logging.getLogger("zhange.migrate")


class UnversionedSchemaError(RuntimeError):
    """The server database holds app tables but no alembic_version; startup will not touch it."""


_PRE_ALEMBIC_HELP = (
    "数据库里有 users 表却没有 alembic_version，启动不会改动这种库。"
    "若是 v0.1.1–v0.1.3（Alembic 之前）建的库：先备份，在 backend/ 执行 "
    "`alembic stamp 20260731_0001` 后重启，会从基线升级到最新；"
    "v0.1.0 的库先删掉 CS2 表与列，见 backend/alembic/README.md「Alembic 之前的旧库」。"
    "若这是别的应用在用的库，请给战鸽数据单独建一个库。"
)

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
    not drift, unless it contradicts a scalar Python default: raw SQL that omits the column
    would store a value the app never writes. A model server_default the DB lacks is still
    reported.
    """
    python_default = metadata_column.default
    if metadata_default is None and python_default is not None:
        value = python_default.arg if python_default.is_scalar else None
        if inspected_default is None or not isinstance(value, (bool, int, float, str, enum.Enum)):
            return False
        return not _same_literal(value, inspected_default)
    return None


def _same_literal(value: object, reflected: str) -> bool:
    text = reflected.strip()
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        text = text[1:-1].replace("''", "'")
    text = {"true": "1", "false": "0"}.get(text.lower(), text)
    if isinstance(value, enum.Enum):
        value = value.value
    if isinstance(value, bool):
        return text == ("1" if value else "0")
    if isinstance(value, (int, float)):
        try:
            return float(text) == float(value)
        except ValueError:
            return False
    return text == str(value)


def _refuse_unversioned(tables: set[str]) -> None:
    if "users" in tables:
        raise UnversionedSchemaError(_PRE_ALEMBIC_HELP)
    leftover = sorted(set(_REQUIRED_TABLES) & tables)
    if leftover:
        raise UnversionedSchemaError(
            "Incomplete database without users/alembic_version; "
            f"leftover tables: {', '.join(leftover)}. "
            "Restore a backup or drop these tables before starting."
        )


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
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables:
        _refuse_unversioned(tables)
    cfg = _alembic_config()

    try:
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

    # Upgrades that started at a UTC-era revision were marked utc_pending inside Alembic (env.py).
    record_time_storage_origin(engine, utc_era=False)
    logger.info("Database migrations are up to date")


def run_migrations() -> None:
    """Apply pending migrations; a new SQLite file is built with create_all and stamped."""
    engine = get_engine()
    before = current_revision(engine)
    if engine.dialect.name == "sqlite":
        _run_sqlite_schema(engine)
    else:
        _run_server_schema(engine)
    after = current_revision(engine)
    if after != before:
        logger.info("database schema revision %s -> %s", before or "(none)", after)
