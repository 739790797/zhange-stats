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


def _repair_known_schema_drift() -> None:
    """Fix drift from the v0.2.37 dual-0056 collision (wrong revision applied)."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "minecraft_server_profiles" in tables:
        cols = {c["name"] for c in inspector.get_columns("minecraft_server_profiles")}
        if "public_host" in cols or "public_port" in cols:
            logger.warning(
                "Repairing minecraft_server_profiles public_* still present after 0056"
            )
            with engine.begin() as conn:
                if "public_host" in cols and "public_port" in cols:
                    row = conn.execute(
                        text(
                            "SELECT public_host, public_port "
                            "FROM minecraft_server_profiles WHERE id = 1"
                        )
                    ).mappings().first()
                    if row:
                        host = (row["public_host"] or "").strip()
                        try:
                            port = int(row["public_port"] or 25565)
                        except (TypeError, ValueError):
                            port = 25565
                        if port < 1 or port > 65535:
                            port = 25565
                        if host or port != 25565:
                            cfg_row = conn.execute(
                                text(
                                    "SELECT value FROM system_configs "
                                    "WHERE `key` = 'integrations'"
                                )
                            ).mappings().first()
                            import json

                            stored: dict = {}
                            if cfg_row:
                                try:
                                    parsed = json.loads(cfg_row["value"] or "{}")
                                except json.JSONDecodeError:
                                    parsed = {}
                                if isinstance(parsed, dict):
                                    stored = parsed
                            if host:
                                stored.setdefault("minecraft_public_host", host)
                            stored.setdefault("minecraft_public_port", port)
                            payload = json.dumps(stored, ensure_ascii=False)
                            if cfg_row:
                                conn.execute(
                                    text(
                                        "UPDATE system_configs SET value = :v "
                                        "WHERE `key` = 'integrations'"
                                    ),
                                    {"v": payload},
                                )
                            else:
                                conn.execute(
                                    text(
                                        "INSERT INTO system_configs (`key`, value) "
                                        "VALUES ('integrations', :v)"
                                    ),
                                    {"v": payload},
                                )
                if "public_port" in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE minecraft_server_profiles DROP COLUMN public_port"
                        )
                    )
                if "public_host" in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE minecraft_server_profiles DROP COLUMN public_host"
                        )
                    )

    if "register_challenges" in tables:
        cols = {c["name"] for c in inspector.get_columns("register_challenges")}
        pk = inspector.get_pk_constraint("register_challenges") or {}
        pk_cols = list(pk.get("constrained_columns") or [])
        if "purpose" not in cols or pk_cols != ["email", "purpose"]:
            logger.warning("Repairing register_challenges to (email, purpose) PK")
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS register_challenges"))
                conn.execute(
                    text(
                        "CREATE TABLE register_challenges ("
                        "email VARCHAR(128) NOT NULL, "
                        "purpose VARCHAR(16) NOT NULL, "
                        "code VARCHAR(16) NOT NULL, "
                        "expires_at DATETIME NOT NULL, "
                        "PRIMARY KEY (email, purpose)"
                        ")"
                    )
                )


def run_migrations() -> None:
    """Apply pending migrations; stamp existing create_all databases once."""
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
    except Exception as exc:
        msg = str(exc)
        if "present more than once" in msg or "overlaps with other requested revisions" in msg:
            raise RuntimeError(
                "Alembic 修订号冲突（常见于 v0.2.37 双 0056）。"
                "请在主机执行应急更新：\n"
                "curl -fsSL https://raw.githubusercontent.com/739790797/zhange-stats/main/"
                "scripts/emergency_update.sh | sudo SOURCE_REF=main bash"
            ) from exc
        raise

    _repair_known_schema_drift()
    _drop_obsolete_tables()
    logger.info("Database migrations are up to date")
