"""塔科夫用户战局日志：本机解析后的摘要落库，不含原文。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserRaidLog
from app.models.user import User

IMPORT_MAX = 500
FOLDER_MAX = 128
RAID_ID_MAX = 16
LOCATION_MAX = 64
MAP_ID_MAX = 32
MAP_LABEL_MAX = 32
MODE_MAX = 16
CLOCK_MAX = 32
DEDUPE_MAX = 220


class TarkovRaidLogsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clip(raw: Any, limit: int) -> str:
    return str(raw or "").strip()[:limit]


def raid_dedupe_key(
    folder: str,
    raid_id: str,
    started_at: str,
    map_id: str,
    aborted: bool,
) -> str:
    if raid_id:
        return f"{folder}|{raid_id}"[:DEDUPE_MAX]
    return f"{folder}|{started_at}|{map_id}|{'1' if aborted else '0'}"[:DEDUPE_MAX]


def _keep_raid(item: dict[str, Any]) -> bool:
    if item.get("raid_id") or item.get("started_at") or item.get("ended_at"):
        return True
    return bool(item.get("aborted") and item.get("map_id"))


def normalize_raid(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    folder = _clip(raw.get("folder"), FOLDER_MAX)
    raid_id = _clip(raw.get("raid_id"), RAID_ID_MAX).upper()
    started_at = _clip(raw.get("started_at"), CLOCK_MAX)
    ended_at = _clip(raw.get("ended_at"), CLOCK_MAX)
    map_id = _clip(raw.get("map_id"), MAP_ID_MAX)
    aborted = bool(raw.get("aborted"))
    item = {
        "folder": folder,
        "raid_id": raid_id,
        "location": _clip(raw.get("location"), LOCATION_MAX),
        "map_id": map_id,
        "map_label": _clip(raw.get("map_label"), MAP_LABEL_MAX),
        "raid_mode": _clip(raw.get("raid_mode"), MODE_MAX).lower(),
        "session_mode": _clip(raw.get("session_mode"), MODE_MAX).lower(),
        "started_at": started_at,
        "ended_at": ended_at,
        "reconnected": bool(raw.get("reconnected")),
        "aborted": aborted,
        "dedupe_key": raid_dedupe_key(folder, raid_id, started_at, map_id, aborted),
    }
    if not _keep_raid(item):
        return None
    return item


def upsert_raids(
    db: Session,
    user: User,
    raids: list[Any],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    stamp = now or now_naive()
    incoming: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raids or []:
        item = normalize_raid(raw)
        if item is None or item["dedupe_key"] in seen:
            continue
        seen.add(item["dedupe_key"])
        incoming.append(item)
        if len(incoming) >= IMPORT_MAX:
            break
    if not incoming:
        return {"inserted": 0, "updated": 0, "skipped": 0, "total": 0}

    keys = [item["dedupe_key"] for item in incoming]
    existing_rows = (
        db.query(TarkovUserRaidLog)
        .filter(
            TarkovUserRaidLog.user_id == user.id,
            TarkovUserRaidLog.dedupe_key.in_(keys),
        )
        .all()
    )
    by_key = {row.dedupe_key: row for row in existing_rows}
    inserted = 0
    updated = 0
    for item in incoming:
        row = by_key.get(item["dedupe_key"])
        if row is None:
            db.add(
                TarkovUserRaidLog(
                    user_id=user.id,
                    created_at=stamp,
                    updated_at=stamp,
                    **item,
                )
            )
            inserted += 1
            continue
        changed = False
        for field in (
            "folder",
            "raid_id",
            "location",
            "map_id",
            "map_label",
            "raid_mode",
            "session_mode",
            "started_at",
            "ended_at",
            "reconnected",
            "aborted",
        ):
            if getattr(row, field) != item[field]:
                setattr(row, field, item[field])
                changed = True
        if changed:
            row.updated_at = stamp
            updated += 1
    db.flush()
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": max(0, len(raids or []) - len(incoming)),
        "total": inserted + updated,
    }
