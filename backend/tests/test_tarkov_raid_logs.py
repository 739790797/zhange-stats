"""本机解析战局摘要落库：去重、更新、丢弃空行。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserRaidLog
from app.models.user import User, UserRole
from app.services.tarkov import raid_logs as logs


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session) -> User:
    row = User(
        username="a",
        display_name="甲",
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def test_dedupe_key_prefers_raid_id() -> None:
    assert logs.raid_dedupe_key("log_a", "PQXKR6", "t", "woods", False) == "log_a|PQXKR6"
    assert logs.raid_dedupe_key("log_a", "", "t1", "woods", True) == "log_a|t1|woods|1"


def test_upsert_inserts_then_updates_same_raid() -> None:
    db = _session()
    user = _user(db)
    now = now_naive()
    first = logs.upsert_raids(
        db,
        user,
        [
            {
                "folder": "log_2026.08.30_20-00-00",
                "raid_id": "pqxkr6",
                "location": "Shoreline",
                "map_id": "shoreline",
                "map_label": "海岸线",
                "raid_mode": "Online",
                "session_mode": "regular",
                "started_at": "2026-08-30 20:10:00.000",
                "ended_at": "",
                "reconnected": False,
                "aborted": False,
            },
            {"folder": "log_x", "raid_id": "", "aborted": True},
        ],
        now=now,
    )
    assert first == {"inserted": 1, "updated": 0, "skipped": 1, "total": 1}

    again = logs.upsert_raids(
        db,
        user,
        [
            {
                "folder": "log_2026.08.30_20-00-00",
                "raid_id": "PQXKR6",
                "location": "Shoreline",
                "map_id": "shoreline",
                "map_label": "海岸线",
                "raid_mode": "online",
                "session_mode": "regular",
                "started_at": "2026-08-30 20:10:00.000",
                "ended_at": "2026-08-30 20:40:00.000",
                "reconnected": True,
                "aborted": False,
            }
        ],
        now=now,
    )
    assert again["inserted"] == 0
    assert again["updated"] == 1
    row = db.query(TarkovUserRaidLog).one()
    assert row.ended_at == "2026-08-30 20:40:00.000"
    assert row.reconnected is True
    assert row.raid_id == "PQXKR6"
