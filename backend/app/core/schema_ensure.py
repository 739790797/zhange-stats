"""启动时补齐/清理 create_all 无法自动处理的 schema 变更。"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _drop_columns(conn, table: str, columns: set[str], drop: list[str]) -> None:
    for col in drop:
        if col not in columns:
            continue
        try:
            conn.execute(text(f"ALTER TABLE `{table}` DROP COLUMN `{col}`"))
        except Exception:  # noqa: BLE001
            pass


def ensure_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # 废弃表（含 v0.1 未上线的 CS2 对局）
    with engine.begin() as conn:
        for obsolete in (
            "cs2_match_players",
            "cs2_matches",
            "match_records",
            "games",
        ):
            if obsolete in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS `{obsolete}`"))

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "members" in tables:
        columns = {c["name"] for c in inspector.get_columns("members")}
        with engine.begin() as conn:
            if "steam_id" not in columns:
                conn.execute(
                    text("ALTER TABLE members ADD COLUMN steam_id VARCHAR(32) NULL")
                )
                try:
                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX ix_members_steam_id ON members (steam_id)"
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass
            if "steam_persona_name" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE members ADD COLUMN steam_persona_name "
                        "VARCHAR(64) NULL"
                    )
                )
            if "steam_avatar_url" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE members ADD COLUMN steam_avatar_url "
                        "VARCHAR(512) NULL"
                    )
                )
            _drop_columns(
                conn,
                "members",
                columns,
                [
                    "extra_bindings",
                    "cs2_auth_code",
                    "cs2_known_code",
                    "cs2_sync_cursor",
                ],
            )

    if "users" in tables:
        columns = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "email" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(128) NULL"))
                try:
                    conn.execute(
                        text("CREATE UNIQUE INDEX ix_users_email ON users (email)")
                    )
                except Exception:  # noqa: BLE001
                    pass
            if "role" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN role ENUM('user','admin') "
                        "NOT NULL DEFAULT 'user'"
                    )
                )
                if "is_admin" in columns:
                    conn.execute(
                        text("UPDATE users SET role='admin' WHERE is_admin=1")
                    )
            if "email_verified" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN email_verified "
                        "TINYINT(1) NOT NULL DEFAULT 0"
                    )
                )
                if "is_admin" in columns:
                    conn.execute(
                        text(
                            "UPDATE users SET email_verified=1 "
                            "WHERE role='admin' OR is_admin=1"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE users SET email_verified=1 WHERE role='admin'"
                        )
                    )
            # is_admin 已由 Alembic 0019 删除；旧库 stamp 前若仍有列可保留，
            # 不再强制 MODIFY。
            # 验证码已迁至 register_challenges
            _drop_columns(
                conn,
                "users",
                columns,
                ["verify_code", "verify_code_expires_at"],
            )

    # 盒子快照 JSON 含技能/模组，TEXT(64KB) 不够，升级为 LONGTEXT
    if "arknights_box_snapshots" in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE arknights_box_snapshots "
                    "MODIFY COLUMN payload_json LONGTEXT NOT NULL"
                )
            )
