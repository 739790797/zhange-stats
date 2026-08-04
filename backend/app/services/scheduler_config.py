"""定时任务调度配置：数据库优先，.env 兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.system_config import SystemConfig

SCHEDULER_CONFIG_KEY = "scheduler_jobs"

JOB_IDS = (
    "steam_presence",
    "skland_checkin",
    "arknights_box_sync",
    "taygedo_checkin",
    "exilium_checkin",
    "kujiequ_checkin",
)


def _clamp_hour(value: Any) -> int:
    try:
        return max(0, min(23, int(value)))
    except (TypeError, ValueError):
        return 0


def _clamp_minute(value: Any) -> int:
    try:
        return max(0, min(59, int(value)))
    except (TypeError, ValueError):
        return 0


def _clamp_interval(value: Any, default: int = 3) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _env_defaults() -> dict[str, dict[str, Any]]:
    s = get_settings()
    return {
        "steam_presence": {
            "enabled": bool(s.STEAM_POLL_ENABLED),
            "interval_minutes": _clamp_interval(s.STEAM_POLL_INTERVAL_MINUTES, 3),
        },
        "skland_checkin": {
            "enabled": bool(s.SKLAND_CHECKIN_ENABLED),
            "hour": _clamp_hour(s.SKLAND_CHECKIN_HOUR),
            "minute": _clamp_minute(s.SKLAND_CHECKIN_MINUTE),
        },
        "arknights_box_sync": {
            "enabled": bool(s.ARKNIGHTS_BOX_SYNC_ENABLED),
            "hour": _clamp_hour(s.ARKNIGHTS_BOX_SYNC_HOUR),
            "minute": _clamp_minute(s.ARKNIGHTS_BOX_SYNC_MINUTE),
        },
        "taygedo_checkin": {
            "enabled": bool(s.TAYGEDO_CHECKIN_ENABLED),
            "hour": _clamp_hour(s.TAYGEDO_CHECKIN_HOUR),
            "minute": _clamp_minute(s.TAYGEDO_CHECKIN_MINUTE),
        },
        "exilium_checkin": {
            "enabled": bool(s.EXILIUM_CHECKIN_ENABLED),
            "hour": _clamp_hour(s.EXILIUM_CHECKIN_HOUR),
            "minute": _clamp_minute(s.EXILIUM_CHECKIN_MINUTE),
        },
        "kujiequ_checkin": {
            "enabled": bool(s.KUJIEQU_CHECKIN_ENABLED),
            "hour": _clamp_hour(s.KUJIEQU_CHECKIN_HOUR),
            "minute": _clamp_minute(s.KUJIEQU_CHECKIN_MINUTE),
        },
    }


def _normalize_job(job_id: str, raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "enabled": bool(raw.get("enabled", fallback.get("enabled", False))),
    }
    if job_id == "steam_presence":
        out["interval_minutes"] = _clamp_interval(
            raw.get("interval_minutes", fallback.get("interval_minutes", 3)),
            3,
        )
    else:
        out["hour"] = _clamp_hour(raw.get("hour", fallback.get("hour", 0)))
        out["minute"] = _clamp_minute(raw.get("minute", fallback.get("minute", 0)))
    return out


def load_scheduler_config(db: Session) -> dict[str, dict[str, Any]]:
    base = _env_defaults()
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == SCHEDULER_CONFIG_KEY)
        .first()
    )
    if not row:
        return {jid: dict(base[jid]) for jid in JOB_IDS}

    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return {jid: dict(base[jid]) for jid in JOB_IDS}
    if not isinstance(stored, dict):
        return {jid: dict(base[jid]) for jid in JOB_IDS}

    out: dict[str, dict[str, Any]] = {}
    for jid in JOB_IDS:
        fallback = base[jid]
        item = stored.get(jid)
        if isinstance(item, dict):
            out[jid] = _normalize_job(jid, item, fallback)
        else:
            out[jid] = dict(fallback)
    return out


def save_scheduler_config(db: Session, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    current = load_scheduler_config(db)
    jobs_in = payload.get("jobs") if isinstance(payload.get("jobs"), dict) else payload
    if not isinstance(jobs_in, dict):
        jobs_in = {}

    next_cfg: dict[str, dict[str, Any]] = {}
    for jid in JOB_IDS:
        fallback = current[jid]
        item = jobs_in.get(jid)
        if isinstance(item, dict):
            next_cfg[jid] = _normalize_job(jid, item, fallback)
        else:
            next_cfg[jid] = dict(fallback)

    raw = json.dumps(next_cfg, ensure_ascii=False)
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == SCHEDULER_CONFIG_KEY)
        .first()
    )
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=SCHEDULER_CONFIG_KEY, value=raw))
    db.commit()
    return next_cfg
