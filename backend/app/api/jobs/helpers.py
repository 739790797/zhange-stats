from __future__ import annotations

from datetime import datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.jobs.catalog import JOB_CATALOG
from app.api.jobs.schemas import ExecutorOut, ScheduledJobLastRunOut, ScheduledJobOut, ScheduledJobsOut
from app.core.timeutil import BEIJING
from app.models.job_run import JobRun
from app.services.integrations_config import get_steam_api_key
from app.services.platform_features import JOB_FEATURE_IDS, is_feature_enabled
from app.services.scheduler_config import load_scheduler_config
from app.services.scheduler_runtime import APP_EXECUTOR_ID, APP_EXECUTOR_NAME


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


def _job_has_running_run(db: Session, job_id: str) -> bool:
    return (
        db.query(JobRun.id)
        .filter(JobRun.job_key == job_id, JobRun.status == "running")
        .first()
        is not None
    )


def _checkin_log_model(platform: str):
    if platform == "skland":
        from app.models.skland import SklandCheckinLog

        return SklandCheckinLog
    if platform == "taygedo":
        from app.models.taygedo import TaygedoCheckinLog

        return TaygedoCheckinLog
    if platform == "exilium":
        from app.models.exilium import ExiliumCheckinLog

        return ExiliumCheckinLog
    if platform == "kujiequ":
        from app.models.kujiequ import KujiequCheckinLog

        return KujiequCheckinLog
    return None


def _bind_model(platform: str):
    if platform == "skland":
        from app.models.skland import SklandBind

        return SklandBind
    if platform == "taygedo":
        from app.models.taygedo import TaygedoBind

        return TaygedoBind
    if platform == "exilium":
        from app.models.exilium import ExiliumBind

        return ExiliumBind
    if platform == "kujiequ":
        from app.models.kujiequ import KujiequBind

        return KujiequBind
    return None


def _member_label(member) -> str:
    user = getattr(member, "user", None)
    if user is not None:
        return (
            user.display_name
            or user.email
            or user.username
            or f"user#{user.id}"
        )
    return member.nickname or f"member#{member.id}"


def _build_jobs_response(db: Session) -> ScheduledJobsOut:
    from app.main import scheduler

    cfg = load_scheduler_config(db)
    steam_key = get_steam_api_key(db)
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

        kind = str(meta.get("kind") or "cron")
        platform = str(meta.get("platform") or "") or None
        feature_id = JOB_FEATURE_IDS.get(job_id)
        enabled = (
            is_feature_enabled(db, feature_id)
            if feature_id
            else bool(job_cfg.get("enabled"))
        )
        if job_id == "steam_presence" and enabled and not steam_key:
            pass
        elif kind == "user_schedule":
            trigger_type = "interval"
            schedule = "按用户设定 · 每分钟巡检"

        last = lasts.get(job_id)
        last_out = None
        if last is not None:
            last_out = ScheduledJobLastRunOut(
                status=last.status,
                started_at=_fmt_dt(last.started_at),
                finished_at=_fmt_dt(last.finished_at),
                message=(last.message or "")[:300] or None,
            )

        hour_out = None
        minute_out = None
        interval_out = None
        if job_id == "steam_presence":
            interval_out = int(job_cfg.get("interval_minutes") or 3)
        elif kind == "cron":
            hour_out = int(job_cfg.get("hour", 0))
            minute_out = int(job_cfg.get("minute", 0))

        items.append(
            ScheduledJobOut(
                id=job_id,
                name=str(meta["name"]),
                description=str(meta.get("description") or ""),
                kind=kind,
                platform=platform,
                executor_id=APP_EXECUTOR_ID,
                registered=job is not None,
                scheduler_running=running,
                trigger_type=trigger_type,
                schedule=schedule,
                next_run_at=next_run_at,
                config_enabled=enabled,
                interval_minutes=interval_out,
                hour=hour_out,
                minute=minute_out,
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
                executor_id=APP_EXECUTOR_ID,
                registered=True,
                scheduler_running=running,
                trigger_type=trigger_type,
                schedule=schedule,
                next_run_at=_fmt_dt(job.next_run_time),
                config_enabled=None,
                last_run=None,
            )
        )

    platforms = [
        ExecutorOut(id=str(m["platform"]), name=str(m["name"]))
        for m in JOB_CATALOG
        if m.get("platform")
    ]

    return ScheduledJobsOut(
        scheduler_running=running,
        timezone=getattr(BEIJING, "key", None) or "Asia/Shanghai",
        platforms=platforms,
        executors=[ExecutorOut(id=APP_EXECUTOR_ID, name=APP_EXECUTOR_NAME)],
        jobs=items,
    )
