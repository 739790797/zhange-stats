"""定时任务调度配置：config/jobs.json 的 scheduler 段。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.file_config import read_json, write_json

SCHEDULER_CONFIG_KEY = "scheduler_jobs"

JOB_IDS = (
    "steam_presence",
    "minecraft_presence",
    "skland_checkin",
    "arknights_box_sync",
    "arknights_catalog_sync",
    "game_schedule_arknights_sync",
    "game_schedule_endfield_sync",
    "taygedo_checkin",
    "exilium_checkin",
    "kujiequ_checkin",
    "mihoyo_checkin",
    "tarkov_full_sync",
    "ocr_model_sync",
    "texteller_model_sync",
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


def _code_defaults() -> dict[str, dict[str, Any]]:
    return {
        "steam_presence": {"enabled": True, "interval_minutes": 3},
        "minecraft_presence": {"enabled": True, "interval_minutes": 1},
        "skland_checkin": {"enabled": True, "hour": 0, "minute": 1},
        "arknights_box_sync": {"enabled": True, "hour": 0, "minute": 20},
        "arknights_catalog_sync": {"enabled": True, "hour": 4, "minute": 0},
        "game_schedule_arknights_sync": {"enabled": True, "hour": 5, "minute": 0},
        "game_schedule_endfield_sync": {"enabled": True, "hour": 5, "minute": 0},
        "tarkov_full_sync": {"enabled": True, "hour": 4, "minute": 25},
        "ocr_model_sync": {"enabled": True, "hour": 5, "minute": 10},
        "texteller_model_sync": {"enabled": True, "hour": 4, "minute": 50},
        "taygedo_checkin": {"enabled": True, "hour": 0, "minute": 1},
        "exilium_checkin": {"enabled": True, "hour": 0, "minute": 1},
        "kujiequ_checkin": {"enabled": True, "hour": 0, "minute": 1},
        "mihoyo_checkin": {"enabled": True, "hour": 0, "minute": 1},
        "job_runs_prune": {"enabled": True, "hour": 3, "minute": 30, "retention_days": 90},
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


def load_scheduler_config(_db: Session | None = None) -> dict[str, dict[str, Any]]:
    base = _code_defaults()
    blob = read_json("jobs") or {}
    stored = blob.get("scheduler") if isinstance(blob.get("scheduler"), dict) else blob
    if not isinstance(stored, dict):
        return {jid: dict(base[jid]) for jid in JOB_IDS}

    out: dict[str, dict[str, Any]] = {}
    for jid in JOB_IDS:
        fallback = base[jid]
        item = stored.get(jid)
        if not isinstance(item, dict) and jid in (
            "game_schedule_arknights_sync",
            "game_schedule_endfield_sync",
        ):
            legacy = stored.get("game_schedule_sync")
            if isinstance(legacy, dict):
                item = legacy
        if not isinstance(item, dict) and jid == "ocr_model_sync":
            legacy = stored.get("tarkov_key_ocr_sync")
            if isinstance(legacy, dict):
                item = legacy
        if isinstance(item, dict):
            out[jid] = _normalize_job(jid, item, fallback)
        else:
            out[jid] = dict(fallback)
    return out


def save_scheduler_config(
    _db: Session | None,
    payload: dict[str, Any],
    *,
    commit: bool = True,
) -> dict[str, dict[str, Any]]:
    current = load_scheduler_config(_db)
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

    blob = read_json("jobs") or {}
    blob["scheduler"] = next_cfg
    write_json("jobs", blob)
    return next_cfg
