from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_url = settings.DATABASE_URL
_is_mysql = _url.startswith("mysql")
_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}
if _is_mysql:
    _engine_kwargs.update(
        pool_size=max(1, int(settings.DB_POOL_SIZE)),
        max_overflow=max(0, int(settings.DB_MAX_OVERFLOW)),
        pool_timeout=max(1, int(settings.DB_POOL_TIMEOUT)),
        connect_args={"charset": "utf8mb4"},
    )

engine = create_engine(_url, **_engine_kwargs)


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


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
