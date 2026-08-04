"""管理员：查看 / 配置系统定时任务。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.timeutil import BEIJING
from app.models.job_run import JobRun
from app.models.user import User
from app.services.dev_config import (
    is_steam_fake_poll,
    save_dev_config,
    steam_fake_module_available,
)
from app.services.integrations_config import get_steam_api_key
from app.services.scheduler_config import load_scheduler_config, save_scheduler_config
from app.services.scheduler_runtime import (
    ensure_local_fake_data_if_needed,
    register_scheduler_jobs,
)

router = APIRouter(prefix="/settings", tags=["settings"])

JOB_CATALOG: list[dict[str, Any]] = [
    {
        "id": "steam_presence",
        "name": "Steam 在线状态轮询",
        "description": "轮询圈子成员 Steam 在线状态与游玩记录",
        "kind": "interval",
    },
    {
        "id": "skland_checkin",
        "name": "森空岛每日签到",
        "description": "明日方舟 / 终末地社区签到",
        "kind": "cron",
    },
    {
        "id": "arknights_box_sync",
        "name": "明日方舟盒子日更",
        "description": "同步干员练度快照（技能 / 模组等）",
        "kind": "cron",
    },
    {
        "id": "taygedo_checkin",
        "name": "塔吉多每日签到",
        "description": "异环官方社区签到",
        "kind": "cron",
    },
    {
        "id": "exilium_checkin",
        "name": "追放社区每日签到",
        "description": "少女前线2：追放社区签到与每日任务",
        "kind": "cron",
    },
    {
        "id": "kujiequ_checkin",
        "name": "库街区每日签到",
        "description": "库街区社区签到 + 鸣潮 / 战双游戏签到",
        "kind": "cron",
    },
]


class ScheduledJobLastRunOut(BaseModel):
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None


class ScheduledJobOut(BaseModel):
    id: str
    name: str
    description: str = ""
    kind: str = "cron"
    registered: bool = False
    scheduler_running: bool = False
    trigger_type: str | None = None
    schedule: str | None = None
    next_run_at: str | None = None
    config_enabled: bool | None = None
    interval_minutes: int | None = None
    hour: int | None = None
    minute: int | None = None
    last_run: ScheduledJobLastRunOut | None = None


class ScheduledJobsOut(BaseModel):
    scheduler_running: bool = False
    timezone: str = "Asia/Shanghai"
    steam_fake_poll: bool = False
    steam_fake_available: bool = False
    jobs: list[ScheduledJobOut] = Field(default_factory=list)


class JobConfigUpdateItem(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)


class ScheduledJobsUpdate(BaseModel):
    jobs: dict[str, JobConfigUpdateItem] = Field(default_factory=dict)
    steam_fake_poll: bool | None = None


def _fmt_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=BEIJING)
    else:
        value = value.astimezone(BEIJING)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _describe_trigger(trigger: Any) -> tuple[str, str]:
    if isinstance(trigger, CronTrigger):
        fields = {
            f.name: str(f)
            for f in trigger.fields
            if f.name in {"hour", "minute", "day", "day_of_week", "month"}
        }
        hour = fields.get("hour", "*")
        minute = fields.get("minute", "*")
        if hour.isdigit() and minute.isdigit():
            schedule = f"每天 {int(hour):02d}:{int(minute):02d}"
        else:
            schedule = f"cron hour={hour} minute={minute}"
        tz = getattr(trigger, "timezone", None)
        if tz is not None:
            schedule += f"（{getattr(tz, 'key', tz)}）"
        return "cron", schedule
    if isinstance(trigger, IntervalTrigger):
        seconds = int(trigger.interval.total_seconds())
        if seconds % 3600 == 0:
            schedule = f"每 {seconds // 3600} 小时"
        elif seconds % 60 == 0:
            schedule = f"每 {seconds // 60} 分钟"
        else:
            schedule = f"每 {seconds} 秒"
        return "interval", schedule
    return type(trigger).__name__.replace("Trigger", "").lower() or "unknown", str(
        trigger
    )


def _last_runs_by_key(db: Session, keys: list[str]) -> dict[str, JobRun]:
    if not keys:
        return {}
    rows = (
        db.query(JobRun)
        .filter(JobRun.job_key.in_(keys))
        .order_by(desc(JobRun.started_at))
        .limit(len(keys) * 5)
        .all()
    )
    out: dict[str, JobRun] = {}
    for row in rows:
        if row.job_key not in out:
            out[row.job_key] = row
    return out


def _build_jobs_response(db: Session) -> ScheduledJobsOut:
    from app.main import scheduler

    cfg = load_scheduler_config(db)
    steam_key = get_steam_api_key(db)
    fake_poll = is_steam_fake_poll(db)
    fake_available = steam_fake_module_available()
    running = bool(scheduler.running)
    registered = {job.id: job for job in scheduler.get_jobs()}
    lasts = _last_runs_by_key(db, [m["id"] for m in JOB_CATALOG])

    items: list[ScheduledJobOut] = []
    for meta in JOB_CATALOG:
        job_id = str(meta["id"])
        job = registered.get(job_id)
        job_cfg = cfg.get(job_id) or {}
        trigger_type = None
        schedule = None
        next_run_at = None
        if job is not None:
            trigger_type, schedule = _describe_trigger(job.trigger)
            next_run_at = _fmt_dt(job.next_run_time)

        enabled = bool(job_cfg.get("enabled"))
        if job_id == "steam_presence":
            if fake_poll:
                enabled = True
            elif enabled and not steam_key:
                # 配置开启但无 Key：视为未真正启用
                pass

        last = lasts.get(job_id)
        last_out = None
        if last is not None:
            last_out = ScheduledJobLastRunOut(
                status=last.status,
                started_at=_fmt_dt(last.started_at),
                finished_at=_fmt_dt(last.finished_at),
                message=(last.message or "")[:300] or None,
            )

        items.append(
            ScheduledJobOut(
                id=job_id,
                name=str(meta["name"]),
                description=str(meta.get("description") or ""),
                kind=str(meta.get("kind") or "cron"),
                registered=job is not None,
                scheduler_running=running,
                trigger_type=trigger_type,
                schedule=schedule,
                next_run_at=next_run_at,
                config_enabled=enabled,
                interval_minutes=(
                    int(job_cfg.get("interval_minutes") or 3)
                    if job_id == "steam_presence"
                    else None
                ),
                hour=(
                    None
                    if job_id == "steam_presence"
                    else int(job_cfg.get("hour", 0))
                ),
                minute=(
                    None
                    if job_id == "steam_presence"
                    else int(job_cfg.get("minute", 0))
                ),
                last_run=last_out,
            )
        )

    known = {m["id"] for m in JOB_CATALOG}
    for job_id, job in registered.items():
        if job_id in known:
            continue
        trigger_type, schedule = _describe_trigger(job.trigger)
        items.append(
            ScheduledJobOut(
                id=job_id,
                name=job_id,
                description="未登记的任务",
                kind="unknown",
                registered=True,
                scheduler_running=running,
                trigger_type=trigger_type,
                schedule=schedule,
                next_run_at=_fmt_dt(job.next_run_time),
                config_enabled=None,
                last_run=None,
            )
        )

    return ScheduledJobsOut(
        scheduler_running=running,
        timezone=getattr(BEIJING, "key", None) or "Asia/Shanghai",
        steam_fake_poll=fake_poll,
        steam_fake_available=fake_available,
        jobs=items,
    )


@router.get("/jobs", response_model=ScheduledJobsOut)
def list_scheduled_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ScheduledJobsOut:
    return _build_jobs_response(db)


@router.put("/jobs", response_model=ScheduledJobsOut)
def update_scheduled_jobs(
    body: ScheduledJobsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ScheduledJobsOut:
    from app.main import scheduler

    reload_needed = False

    if body.steam_fake_poll is not None:
        if body.steam_fake_poll and not steam_fake_module_available():
            raise HTTPException(
                status_code=400,
                detail="本环境未包含 local_dev.steam_fake，无法开启假监控",
            )
        save_dev_config(db, {"steam_fake_poll": body.steam_fake_poll})
        if body.steam_fake_poll:
            ensure_local_fake_data_if_needed(db)
        reload_needed = True

    fake_poll = is_steam_fake_poll(db)
    payload_jobs: dict[str, Any] = {}
    for job_id, item in body.jobs.items():
        data = item.model_dump(exclude_none=True)
        if fake_poll and job_id == "steam_presence":
            # 假监控开启时强制跑 Steam 任务，忽略 UI 对其 enabled 的关闭
            data.pop("enabled", None)
        if data:
            payload_jobs[job_id] = data

    if payload_jobs:
        save_scheduler_config(db, {"jobs": payload_jobs})
        reload_needed = True

    if reload_needed:
        register_scheduler_jobs(scheduler, db, run_steam_once=False)

    return _build_jobs_response(db)
