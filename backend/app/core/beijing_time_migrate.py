"""一次性：把原先按 UTC 写入的业务时间改为北京墙钟（+8 小时）。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

_MARKER_KEY = "time_storage"
_MARKER_VALUE = "beijing_v1"

# 仅迁移应用曾用 datetime.now(UTC) 写入的列；不动 created_at/joined_at（server_default）
_SHIFTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("presence_segments", ("started_at", "last_seen_at", "ended_at")),
    ("play_sessions", ("started_at", "last_seen_at", "ended_at")),
    ("job_runs", ("started_at", "finished_at")),
    ("members", ("steam_friends_synced_at",)),
    ("steam_friend_edges", ("synced_at",)),
    ("steam_apps", ("fetched_at", "details_fetched_at")),
    ("register_challenges", ("expires_at",)),
)


def ensure_beijing_time_storage(db: Session, engine: Engine) -> None:
    row = db.get(SystemConfig, _MARKER_KEY)
    if row and row.value.strip() == _MARKER_VALUE:
        return

    logger.info("migrating business timestamps UTC -> Beijing (+8h)")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, cols in _SHIFTS:
            if table not in table_names:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col in cols:
                if col not in existing:
                    continue
                conn.execute(
                    text(
                        f"UPDATE `{table}` SET `{col}` = DATE_ADD(`{col}`, INTERVAL 8 HOUR) "
                        f"WHERE `{col}` IS NOT NULL"
                    )
                )

    if row is None:
        db.add(SystemConfig(key=_MARKER_KEY, value=_MARKER_VALUE))
    else:
        row.value = _MARKER_VALUE
    db.commit()
    logger.info("business timestamps now stored as Beijing wall clock")
