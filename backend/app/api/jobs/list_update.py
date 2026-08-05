"""管理员：查看 / 配置系统定时任务。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.jobs.catalog import JOB_CATALOG
from app.api.jobs.helpers import _build_jobs_response
from app.api.jobs.schemas import ScheduledJobsOut, ScheduledJobsUpdate
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.scheduler_config import save_scheduler_config
from app.services.scheduler_runtime import register_scheduler_jobs

router = APIRouter()


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
