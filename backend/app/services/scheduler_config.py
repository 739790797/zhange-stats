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
    "minecraft_presence",
    "skland_checkin",
    "arknights_box_sync",
    "arknights_catalog_sync",
    "taygedo_checkin",
    "exilium_checkin",
    "kujiequ_checkin",
    "tarkov_items_sync",
    "tarkov_tasks_sync",
    "tarkov_traders_sync",
    "tarkov_bosses_sync",
    "tarkov_guides_sync",
    "job_runs_prune",
)

INTERVAL_JOB_IDS = frozenset({"steam_presence", "minecraft_presence"})


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
        "minecraft_presence": {
            "enabled": True,
            "interval_minutes": _clamp_interval(
                getattr(s, "MINECRAFT_POLL_INTERVAL_MINUTES", 1), 1
            ),
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
        "arknights_catalog_sync": {
            "enabled": bool(s.ARKNIGHTS_CATALOG_SYNC_ENABLED),
            "hour": _clamp_hour(s.ARKNIGHTS_CATALOG_SYNC_HOUR),
            "minute": _clamp_minute(s.ARKNIGHTS_CATALOG_SYNC_MINUTE),
        },
        "tarkov_items_sync": {
            "enabled": bool(
                getattr(s, "TARKOV_ITEMS_SYNC_ENABLED", True)
                and getattr(s, "TARKOV_AMMO_SYNC_ENABLED", True)
            ),
            "hour": _clamp_hour(
                getattr(s, "TARKOV_ITEMS_SYNC_HOUR", None) or s.TARKOV_AMMO_SYNC_HOUR
            ),
            "minute": _clamp_minute(
                getattr(s, "TARKOV_ITEMS_SYNC_MINUTE", None) or s.TARKOV_AMMO_SYNC_MINUTE
            ),
        },
        "tarkov_tasks_sync": {
            "enabled": bool(getattr(s, "TARKOV_TASKS_SYNC_ENABLED", True)),
            "hour": _clamp_hour(getattr(s, "TARKOV_TASKS_SYNC_HOUR", 4)),
            "minute": _clamp_minute(getattr(s, "TARKOV_TASKS_SYNC_MINUTE", 35)),
        },
        "tarkov_traders_sync": {
            "enabled": bool(getattr(s, "TARKOV_TRADERS_SYNC_ENABLED", True)),
            "hour": _clamp_hour(getattr(s, "TARKOV_TRADERS_SYNC_HOUR", 4)),
            "minute": _clamp_minute(getattr(s, "TARKOV_TRADERS_SYNC_MINUTE", 40)),
        },
        "tarkov_bosses_sync": {
            "enabled": bool(getattr(s, "TARKOV_BOSSES_SYNC_ENABLED", True)),
            "hour": _clamp_hour(getattr(s, "TARKOV_BOSSES_SYNC_HOUR", 4)),
            "minute": _clamp_minute(getattr(s, "TARKOV_BOSSES_SYNC_MINUTE", 45)),
        },
        "tarkov_guides_sync": {
            "enabled": bool(getattr(s, "TARKOV_GUIDES_SYNC_ENABLED", True)),
            "hour": _clamp_hour(getattr(s, "TARKOV_GUIDES_SYNC_HOUR", 4)),
            "minute": _clamp_minute(getattr(s, "TARKOV_GUIDES_SYNC_MINUTE", 50)),
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
        "job_runs_prune": {
            "enabled": True,
            "hour": 3,
            "minute": 30,
            "retention_days": 90,
        },
    }


def _clamp_retention_days(value: Any, default: int = 90) -> int:
    try:
        return max(7, min(3650, int(value)))
    except (TypeError, ValueError):
        return default


def _normalize_job(job_id: str, raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "enabled": bool(raw.get("enabled", fallback.get("enabled", False))),
    }
    if job_id in INTERVAL_JOB_IDS:
        default = 3 if job_id == "steam_presence" else 1
        out["interval_minutes"] = _clamp_interval(
            raw.get("interval_minutes", fallback.get("interval_minutes", default)),
            default,
        )
    else:
        out["hour"] = _clamp_hour(raw.get("hour", fallback.get("hour", 0)))
        out["minute"] = _clamp_minute(raw.get("minute", fallback.get("minute", 0)))
    if job_id == "job_runs_prune":
        out["retention_days"] = _clamp_retention_days(
            raw.get("retention_days", fallback.get("retention_days", 90)),
            90,
        )
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
        if not isinstance(item, dict) and jid == "tarkov_items_sync":
            # 旧分 job → 合并 items
            for legacy in ("tarkov_ammo_sync", "tarkov_gun_sync"):
                if isinstance(stored.get(legacy), dict):
                    item = stored[legacy]
                    break
        if isinstance(item, dict):
            out[jid] = _normalize_job(jid, item, fallback)
        else:
            out[jid] = dict(fallback)
    return out


def save_scheduler_config(
    db: Session,
    payload: dict[str, Any],
    *,
    commit: bool = True,
) -> dict[str, dict[str, Any]]:
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
    if commit:
        db.commit()
    else:
        db.flush()
    return next_cfg
