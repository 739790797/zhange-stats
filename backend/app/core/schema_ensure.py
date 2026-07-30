"""启动时补齐/清理 create_all 无法自动处理的 schema 变更。"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # 废弃的战绩体系表
    with engine.begin() as conn:
        for obsolete in ("match_records", "games"):
            if obsolete in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS `{obsolete}`"))

    inspector = inspect(engine)
    tables = inspector.get_table_names()

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
            if "extra_bindings" in columns:
                try:
                    conn.execute(text("ALTER TABLE members DROP COLUMN extra_bindings"))
                except Exception:  # noqa: BLE001
                    pass

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
                conn.execute(
                    text(
                        "UPDATE users SET email_verified=1 "
                        "WHERE role='admin' OR is_admin=1"
                    )
                )
            if "verify_code" not in columns:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN verify_code VARCHAR(16) NULL")
                )
            if "verify_code_expires_at" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN verify_code_expires_at "
                        "DATETIME(6) NULL"
                    )
                )
            try:
                conn.execute(
                    text(
                        "ALTER TABLE users MODIFY COLUMN is_admin "
                        "TINYINT(1) NOT NULL DEFAULT 0"
                    )
                )
            except Exception:  # noqa: BLE001
                pass
