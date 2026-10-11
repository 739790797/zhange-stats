import logging
import sqlite3
from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.config import get_settings
from app.core.file_config import database_is_configured, resolve_database_url

logger = logging.getLogger("zhange.db")

SQLITE_BUSY_TIMEOUT_MS = 10_000
_WAL_LOG_KEY = "db.sqlite_wal"

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


class Base(DeclarativeBase):
    pass


class DatabaseNotConfigured(RuntimeError):
    """No config/database.json and no DATABASE_URL in the environment."""


def _sqlite_is_file(url: str) -> bool:
    parsed = make_url(url)
    database = (parsed.database or "").strip()
    if not database or database == ":memory:" or database.startswith("file::memory:"):
        return False
    return parsed.query.get("mode") != "memory"


def _install_sqlite_pragmas(engine: Engine, *, file_db: bool) -> None:
    """Per-engine on purpose: Alembic builds its own engine and must keep foreign keys off."""

    def _on_connect(dbapi_conn, connection_record) -> None:
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
            if file_db:
                mode = ""
                try:
                    row = cursor.execute("PRAGMA journal_mode = WAL").fetchone()
                    mode = str(row[0] if row else "").lower()
                except sqlite3.Error as exc:
                    mode = f"error: {exc}"
                if mode == "wal":
                    # NORMAL is only crash-safe with WAL; rollback-journal mode keeps FULL.
                    cursor.execute("PRAGMA synchronous = NORMAL")
                    clear_log_until_change(_WAL_LOG_KEY)
                else:
                    log_until_change(
                        logger,
                        _WAL_LOG_KEY,
                        "SQLite WAL unavailable (journal_mode=%s); keeping rollback journal",
                        mode or "unknown",
                    )
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()

    event.listen(engine, "connect", _on_connect)


def prepare_migration_engine(engine: Engine) -> None:
    """Alembic engine: SQLite batch mode rebuilds tables via DROP TABLE, which would cascade with FKs on."""
    if engine.dialect.name != "sqlite":
        return

    def _on_connect(dbapi_conn, connection_record) -> None:
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
            cursor.execute("PRAGMA foreign_keys = OFF")
        finally:
            cursor.close()

    event.listen(engine, "connect", _on_connect)


def _build_engine(url: str) -> Engine:
    settings = get_settings()
    kwargs: dict = {
        "pool_pre_ping": True,
    }
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = connect_args
    elif url.startswith("mysql"):
        kwargs.update(
            pool_recycle=3600,
            pool_size=max(1, int(settings.DB_POOL_SIZE)),
            max_overflow=max(0, int(settings.DB_MAX_OVERFLOW)),
            pool_timeout=max(1, int(settings.DB_POOL_TIMEOUT)),
            connect_args={"charset": "utf8mb4"},
        )
    else:
        kwargs["pool_recycle"] = 3600
    built = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _install_sqlite_pragmas(built, file_db=_sqlite_is_file(url))
    return built


@event.listens_for(Engine, "connect")
def _set_session_timezone(dbapi_conn, connection_record) -> None:
    """会话时区固定为北京，使 CURRENT_TIMESTAMP 与业务写入一致（仅 MySQL）。"""
    dialect = getattr(getattr(connection_record, "dialect", None), "name", "") or ""
    if dialect != "mysql":
        return
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SET time_zone = '+08:00'")
    finally:
        cursor.close()


def configure_engine(url: str | None = None) -> Engine:
    global _engine, _SessionLocal
    resolved = (url or resolve_database_url() or "").strip()
    if not resolved:
        raise DatabaseNotConfigured("database is not configured")
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:  # noqa: BLE001
            pass
    _engine = _build_engine(resolved)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    if not database_is_configured():
        raise DatabaseNotConfigured("database is not configured")
    return configure_engine()


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


class _EngineProxy:
    def __getattr__(self, name: str):
        return getattr(get_engine(), name)

    def __bool__(self) -> bool:
        return _engine is not None or database_is_configured()


class _SessionFactory:
    def __call__(self, **kwargs) -> Session:
        return get_sessionmaker()(**kwargs)

    def configure(self, **kwargs) -> None:
        get_sessionmaker().configure(**kwargs)


engine = _EngineProxy()
SessionLocal = _SessionFactory()


def get_db() -> Generator[Session, None, None]:
    if not database_is_configured() and _engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="系统尚未初始化，请先完成安装向导",
            headers={"X-Setup": "1"},
        )
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
