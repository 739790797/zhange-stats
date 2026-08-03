"""管理员：查看系统定时任务。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.timeutil import BEIJING
from app.models.job_run import JobRun
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

# 与 APScheduler job id / JobRun.job_key 对齐
JOB_CATALOG: list[dict[str, Any]] = [
    {
        "id": "steam_presence",
        "name": "Steam 在线状态轮询",
        "description": "轮询圈子成员 Steam 在线状态与游玩记录",
        "config_enabled_attr": None,  # 由 STEAM_POLL_ENABLED / STEAM_FAKE_POLL 决定
    },
    {
        "id": "skland_checkin",
        "name": "森空岛每日签到",
        "description": "明日方舟 / 终末地社区签到",
        "config_enabled_attr": "SKLAND_CHECKIN_ENABLED",
    },
    {
        "id": "arknights_box_sync",
        "name": "明日方舟盒子日更",
        "description": "同步干员练度快照（技能 / 模组等）",
        "config_enabled_attr": "ARKNIGHTS_BOX_SYNC_ENABLED",
    },
    {
        "id": "taygedo_checkin",
        "name": "塔吉多每日签到",
        "description": "异环官方社区签到",
        "config_enabled_attr": "TAYGEDO_CHECKIN_ENABLED",
    },
    {
        "id": "exilium_checkin",
        "name": "追放社区每日签到",
        "description": "少女前线2：追放社区签到与每日任务",
        "config_enabled_attr": "EXILIUM_CHECKIN_ENABLED",
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
    registered: bool = False
    scheduler_running: bool = False
    trigger_type: str | None = None
    schedule: str | None = None
    next_run_at: str | None = None
    config_enabled: bool | None = None
    last_run: ScheduledJobLastRunOut | None = None


class ScheduledJobsOut(BaseModel):
    scheduler_running: bool = False
    timezone: str = "Asia/Shanghai"
    jobs: list[ScheduledJobOut] = Field(default_factory=list)


def _fmt_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # APScheduler 在部分触发器下可能给 naive；按北京时间展示
        value = value.replace(tzinfo=BEIJING)
    else:
        value = value.astimezone(BEIJING)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _describe_trigger(trigger: Any) -> tuple[str, str]:
    if isinstance(trigger, CronTrigger):
        fields = {f.name: str(f) for f in trigger.fields if f.name in {"hour", "minute", "day", "day_of_week", "month"}}
        hour = fields.get("hour", "*")
        minute = fields.get("minute", "*")
        # 常见日更：每天 HH:MM
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
    return type(trigger).__name__.replace("Trigger", "").lower() or "unknown", str(trigger)


def _config_enabled(job_id: str, meta: dict[str, Any]) -> bool | None:
    settings = get_settings()
    attr = meta.get("config_enabled_attr")
    if attr:
        return bool(getattr(settings, attr, False))
    if job_id == "steam_presence":
        if settings.STEAM_FAKE_POLL:
            return True
        return bool(settings.STEAM_POLL_ENABLED and settings.STEAM_API_KEY)
    return None


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


@router.get("/jobs", response_model=ScheduledJobsOut)
def list_scheduled_jobs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ScheduledJobsOut:
    """列出系统已注册 / 配置中的定时任务。"""
    from app.main import scheduler

    running = bool(scheduler.running)
    registered = {job.id: job for job in scheduler.get_jobs()}
    lasts = _last_runs_by_key(db, [m["id"] for m in JOB_CATALOG])

    items: list[ScheduledJobOut] = []
    for meta in JOB_CATALOG:
        job_id = str(meta["id"])
        job = registered.get(job_id)
        trigger_type = None
        schedule = None
        next_run_at = None
        if job is not None:
            trigger_type, schedule = _describe_trigger(job.trigger)
            next_run_at = _fmt_dt(job.next_run_time)

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
                registered=job is not None,
                scheduler_running=running,
                trigger_type=trigger_type,
                schedule=schedule,
                next_run_at=next_run_at,
                config_enabled=_config_enabled(job_id, meta),
                last_run=last_out,
            )
        )

    # 未在目录中但已注册的任务（兜底）
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
        jobs=items,
    )
