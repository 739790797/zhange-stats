"""管理员：查看 / 配置系统定时任务。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.timeutil import BEIJING
from app.models.job_run import JobRun
from app.models.user import User
from app.services.integrations_config import get_steam_api_key
from app.services.platform_features import (
    CHECKIN_PLATFORM_FEATURES,
    JOB_FEATURE_IDS,
    PLATFORM_SHORT_NAMES,
    is_feature_enabled,
)
from app.services.scheduler_config import JOB_IDS, load_scheduler_config, save_scheduler_config
from app.services.scheduler_runtime import (
    APP_EXECUTOR_ID,
    APP_EXECUTOR_NAME,
    register_scheduler_jobs,
    release_manual_trigger,
    resolve_job_callable,
    try_acquire_manual_trigger,
)

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger("zhange.jobs")

JOB_CATALOG: list[dict[str, Any]] = [
    {
        "id": "steam_presence",
        "name": "Steam 在线状态轮询",
        "description": "轮询圈子成员 Steam 在线状态与游玩记录",
        "kind": "interval",
        "platform": "steam",
    },
    {
        "id": "skland_checkin",
        "name": "森空岛每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "skland",
    },
    {
        "id": "arknights_box_sync",
        "name": "用户干员box",
        "description": "按绑定用户同步森空岛干员练度快照（技能 / 模组等）",
        "kind": "cron",
        "platform": "arknights_box",
    },
    {
        "id": "arknights_catalog_sync",
        "name": "开源图鉴同步",
        "description": "从 yuanyan3060/ArknightsGameResource 同步 character_table",
        "kind": "cron",
        "platform": "arknights_catalog",
    },
    {
        "id": "taygedo_checkin",
        "name": "塔吉多每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "taygedo",
    },
    {
        "id": "exilium_checkin",
        "name": "追放社区每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "exilium",
    },
    {
        "id": "kujiequ_checkin",
        "name": "库街区每日签到",
        "description": "按用户自设时间巡检签到",
        "kind": "user_schedule",
        "platform": "kujiequ",
    },
]

_CHECKIN_PLATFORMS = frozenset({"skland", "taygedo", "exilium", "kujiequ"})
_KNOWN_JOB_IDS = {str(m["id"]) for m in JOB_CATALOG}
_PLATFORM_TO_JOB = {str(m["platform"]): str(m["id"]) for m in JOB_CATALOG if m.get("platform")}



class ExecutorOut(BaseModel):
    id: str
    name: str


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
    platform: str | None = None
    executor_id: str = APP_EXECUTOR_ID
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
    platforms: list[ExecutorOut] = Field(default_factory=list)
    executors: list[ExecutorOut] = Field(default_factory=list)
    jobs: list[ScheduledJobOut] = Field(default_factory=list)


class JobTriggerRequest(BaseModel):
    member_id: int | None = None


class JobTriggerOut(BaseModel):
    accepted: bool = True
    job_id: str
    message: str = "已提交执行"


class JobRunOut(BaseModel):
    id: int
    job_key: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None
    stats: dict[str, Any] | None = None


class JobRunsPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[JobRunOut] = Field(default_factory=list)


class CheckinLogItemOut(BaseModel):
    id: int
    platform: str
    member_id: int
    user_label: str | None = None
    game_code: str
    game_name: str
    role_uid: str
    role_name: str | None = None
    status: str
    message: str | None = None
    awards_text: str | None = None
    checkin_date: str
    checked_at: str | None = None


class CheckinLogsPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CheckinLogItemOut] = Field(default_factory=list)


class JobMemberOptionOut(BaseModel):
    member_id: int
    user_id: int | None = None
    label: str


class UserCheckinTaskOut(BaseModel):
    """用户 × 已绑定平台 = 一条签到任务。"""

    task_key: str
    job_id: str
    platform: str
    platform_name: str
    member_id: int
    user_label: str
    auto_checkin: bool
    checkin_hour: int
    checkin_minute: int
    last_checkin_at: str | None = None
    last_checkin_date: str | None = None
    last_checkin_ok: bool | None = None
    last_checkin_summary: str | None = None
    bound_at: str | None = None


class UserCheckinTasksPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[UserCheckinTaskOut] = Field(default_factory=list)


class JobConfigUpdateItem(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)


class ScheduledJobsUpdate(BaseModel):
    jobs: dict[str, JobConfigUpdateItem] = Field(default_factory=dict)


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

    payload_jobs: dict[str, Any] = {}
    for job_id, item in body.jobs.items():
        # 签到类时间已下放用户；系统级开关只认「任务配置」功能树
        meta = next((m for m in JOB_CATALOG if m["id"] == job_id), None)
        if meta and meta.get("kind") == "user_schedule":
            continue
        data = item.model_dump(exclude_none=True)
        data.pop("enabled", None)
        if data:
            payload_jobs[job_id] = data

    if payload_jobs:
        save_scheduler_config(db, {"jobs": payload_jobs})
        register_scheduler_jobs(scheduler, db, run_steam_once=False)

    return _build_jobs_response(db)


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


@router.get("/jobs/checkin-logs", response_model=CheckinLogsPageOut)
def list_checkin_logs(
    platform: str | None = Query(default=None),
    member_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CheckinLogsPageOut:
    """按平台 / 用户查询签到明细（checkin_logs）。"""
    return query_checkin_logs(
        db,
        platform=platform,
        member_id=member_id,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/members", response_model=list[JobMemberOptionOut])
def list_job_filter_members(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[JobMemberOptionOut]:
    """供任务调度页「按用户」下拉：仅含任一签到平台已绑定的成员。"""
    from app.models.member import Member
    from sqlalchemy.orm import joinedload

    bound_ids: set[int] = set()
    for p in sorted(_CHECKIN_PLATFORMS):
        model = _bind_model(p)
        if model is None:
            continue
        bound_ids.update(
            mid for (mid,) in db.query(model.member_id).all() if mid is not None
        )
    if not bound_ids:
        return []

    members = (
        db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id.in_(bound_ids))
        .order_by(Member.id.asc())
        .all()
    )
    out: list[JobMemberOptionOut] = []
    for m in members:
        user = m.user
        out.append(
            JobMemberOptionOut(
                member_id=m.id,
                user_id=user.id if user else None,
                label=_member_label(m),
            )
        )
    return out


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


@router.get("/jobs/user-tasks", response_model=UserCheckinTasksPageOut)
def list_user_checkin_tasks(
    platform: str | None = Query(default=None),
    member_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserCheckinTasksPageOut:
    """列出所有「用户 × 已绑定平台」签到任务（含用户自设时间）。"""
    return query_user_checkin_tasks(
        db,
        platform=platform,
        member_id=member_id,
        page=page,
        page_size=page_size,
    )


def query_user_checkin_tasks(
    db: Session,
    *,
    platform: str | None = None,
    member_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> UserCheckinTasksPageOut:
    """按平台 / 成员查询用户级日常任务（供管理端与「我的日常」复用）。"""
    from app.models.member import Member
    from sqlalchemy.orm import joinedload

    if platform and platform not in _CHECKIN_PLATFORMS:
        raise HTTPException(status_code=400, detail="不支持的平台")

    platforms = [platform] if platform else sorted(_CHECKIN_PLATFORMS)
    platforms = [
        p
        for p in platforms
        if is_feature_enabled(db, p)
        and is_feature_enabled(db, CHECKIN_PLATFORM_FEATURES.get(p, p))
    ]
    job_by_platform = {
        str(m["platform"]): str(m["id"])
        for m in JOB_CATALOG
        if m.get("kind") == "user_schedule" and m.get("platform")
    }

    items: list[UserCheckinTaskOut] = []
    for p in platforms:
        model = _bind_model(p)
        job_id = job_by_platform.get(p)
        if model is None or not job_id:
            continue
        q = db.query(model).options(joinedload(model.member).joinedload(Member.user))
        if member_id is not None:
            q = q.filter(model.member_id == int(member_id))
        for bind in q.order_by(model.member_id.asc()).all():
            member = bind.member
            items.append(
                UserCheckinTaskOut(
                    task_key=f"{p}:{bind.member_id}",
                    job_id=job_id,
                    platform=p,
                    platform_name=PLATFORM_SHORT_NAMES.get(p, p),
                    member_id=bind.member_id,
                    user_label=_member_label(member)
                    if member
                    else f"member#{bind.member_id}",
                    auto_checkin=bool(bind.auto_checkin),
                    checkin_hour=int(bind.checkin_hour),
                    checkin_minute=int(bind.checkin_minute),
                    last_checkin_at=_fmt_dt(bind.last_checkin_at),
                    last_checkin_date=bind.last_checkin_date.isoformat()
                    if bind.last_checkin_date
                    else None,
                    last_checkin_ok=bind.last_checkin_ok,
                    last_checkin_summary=bind.last_checkin_summary,
                    bound_at=_fmt_dt(bind.bound_at),
                )
            )

    items.sort(
        key=lambda t: (
            t.checkin_hour,
            t.checkin_minute,
            t.platform,
            t.member_id,
        )
    )
    total = len(items)
    start = (page - 1) * page_size
    return UserCheckinTasksPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=items[start : start + page_size],
    )


def query_checkin_logs(
    db: Session,
    *,
    platform: str | None = None,
    member_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CheckinLogsPageOut:
    """按平台 / 成员查询签到明细（供管理端与「我的日常」复用）。"""
    if platform and platform not in _CHECKIN_PLATFORMS:
        raise HTTPException(status_code=400, detail="不支持的平台")

    platforms = [platform] if platform else sorted(_CHECKIN_PLATFORMS)
    from app.models.member import Member
    from sqlalchemy.orm import joinedload

    page_rows: list[tuple[str, Any]]
    total: int

    if len(platforms) == 1:
        p = platforms[0]
        model = _checkin_log_model(p)
        if model is None:
            return CheckinLogsPageOut(total=0, page=page, page_size=page_size, items=[])
        q = db.query(model)
        if member_id is not None:
            q = q.filter(model.member_id == int(member_id))
        total = int(q.count() or 0)
        rows = (
            q.order_by(desc(model.checked_at), desc(model.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        page_rows = [(p, row) for row in rows]
    else:
        total = 0
        merged: list[tuple[str, Any]] = []
        fetch_n = page * page_size
        for p in platforms:
            model = _checkin_log_model(p)
            if model is None:
                continue
            q = db.query(model)
            if member_id is not None:
                q = q.filter(model.member_id == int(member_id))
            total += int(q.count() or 0)
            for row in q.order_by(desc(model.checked_at), desc(model.id)).limit(
                fetch_n
            ).all():
                merged.append((p, row))
        merged.sort(
            key=lambda pair: (
                pair[1].checked_at or datetime.min.replace(tzinfo=BEIJING),
                pair[1].id,
            ),
            reverse=True,
        )
        start = (page - 1) * page_size
        page_rows = merged[start : start + page_size]

    member_ids = {r.member_id for _, r in page_rows}
    members = {
        m.id: m
        for m in db.query(Member)
        .options(joinedload(Member.user))
        .filter(Member.id.in_(member_ids))
        .all()
    } if member_ids else {}

    items = []
    for p, row in page_rows:
        member = members.get(row.member_id)
        items.append(
            CheckinLogItemOut(
                id=row.id,
                platform=p,
                member_id=row.member_id,
                user_label=_member_label(member) if member else None,
                game_code=row.game_code,
                game_name=row.game_name,
                role_uid=row.role_uid,
                role_name=row.role_name,
                status=row.status,
                message=row.message,
                awards_text=row.awards_text,
                checkin_date=row.checkin_date.isoformat()
                if row.checkin_date
                else "",
                checked_at=_fmt_dt(row.checked_at),
            )
        )
    return CheckinLogsPageOut(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.post("/jobs/{job_id}/trigger", response_model=JobTriggerOut)
def trigger_scheduled_job(
    job_id: str,
    body: JobTriggerRequest | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> JobTriggerOut:
    if job_id not in _KNOWN_JOB_IDS and job_id not in JOB_IDS:
        raise HTTPException(status_code=404, detail="未知任务")
    if job_id not in JOB_IDS:
        raise HTTPException(status_code=400, detail="该任务不支持手动执行")

    member_id = body.member_id if body else None
    if member_id is not None:
        meta = next((m for m in JOB_CATALOG if m["id"] == job_id), None)
        if not meta or meta.get("kind") != "user_schedule":
            raise HTTPException(
                status_code=400, detail="仅签到类任务支持按用户手动执行"
            )

    if _job_has_running_run(db, job_id):
        raise HTTPException(status_code=409, detail="任务正在执行中，请稍后再试")

    if not try_acquire_manual_trigger(job_id):
        raise HTTPException(status_code=409, detail="任务正在执行中，请稍后再试")

    try:
        runner = resolve_job_callable(job_id, db, member_id=member_id)
    except KeyError:
        release_manual_trigger(job_id)
        raise HTTPException(status_code=404, detail="未知任务") from None
    except RuntimeError as exc:
        release_manual_trigger(job_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _run() -> None:
        try:
            runner()
        except Exception:  # noqa: BLE001
            logger.exception("manual trigger failed job_id=%s", job_id)
        finally:
            release_manual_trigger(job_id)

    threading.Thread(
        target=_run,
        name=f"job-trigger-{job_id}",
        daemon=True,
    ).start()

    return JobTriggerOut(
        accepted=True,
        job_id=job_id,
        message="已提交执行" if member_id is None else f"已提交用户 {member_id} 的执行",
    )


@router.get("/jobs/{job_id}/runs", response_model=JobRunsPageOut)
def list_job_runs(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> JobRunsPageOut:
    if job_id not in _KNOWN_JOB_IDS and job_id not in JOB_IDS:
        raise HTTPException(status_code=404, detail="未知任务")

    total = (
        db.query(func.count(JobRun.id)).filter(JobRun.job_key == job_id).scalar() or 0
    )
    rows = (
        db.query(JobRun)
        .filter(JobRun.job_key == job_id)
        .order_by(desc(JobRun.started_at), desc(JobRun.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        JobRunOut(
            id=row.id,
            job_key=row.job_key,
            status=row.status,
            started_at=_fmt_dt(row.started_at),
            finished_at=_fmt_dt(row.finished_at),
            message=row.message,
            stats=row.stats,
        )
        for row in rows
    ]
    return JobRunsPageOut(
        total=int(total),
        page=page,
        page_size=page_size,
        items=items,
    )
