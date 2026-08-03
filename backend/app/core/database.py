from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)


@event.listens_for(Engine, "connect")
def _set_session_timezone(dbapi_conn, _connection_record) -> None:
    """会话时区固定为北京，使 CURRENT_TIMESTAMP 与业务写入一致。"""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SET time_zone = '+08:00'")
        cursor.execute("SET NAMES utf8mb4")
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
