"""Run Alembic migrations against the configured database."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.core.database import Base, engine
from app.core.schema_ensure import ensure_schema

logger = logging.getLogger("zhange.migrate")

_OBSOLETE_TABLES = (
    "cs2_match_players",
    "cs2_matches",
    "match_records",
    "games",
)

_REQUIRED_TABLES = (
    "users",
    "members",
    "register_challenges",
    "job_runs",
    "system_configs",
    "play_sessions",
    "presence_segments",
    "steam_friend_edges",
    "steam_apps",
)

_REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "users": frozenset({"email", "role", "email_verified", "is_admin"}),
    "members": frozenset(
        {
            "steam_id",
            "steam_friends_public",
            "steam_friends_synced_at",
            "steam_persona_name",
            "user_id",
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
    return cfg


def _drop_obsolete_tables() -> None:
    with engine.begin() as conn:
        for name in _OBSOLETE_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS `{name}`"))


def _verify_aligned_schema() -> None:
    inspector = inspect(engine)
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

    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    _verify_aligned_schema()


def run_migrations() -> None:
    """Apply pending migrations; stamp existing create_all databases once."""
    cfg = _alembic_config()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "alembic_version" not in tables and "users" in tables:
        logger.info(
            "Existing schema detected without alembic_version; "
            "aligning schema then stamping baseline as applied"
        )
        _align_legacy_schema()
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
        command.upgrade(cfg, "head")

    _drop_obsolete_tables()
    logger.info("Database migrations are up to date")
