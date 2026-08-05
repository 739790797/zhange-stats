from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.jobs.catalog import JOB_CATALOG, _KNOWN_JOB_IDS
from app.api.jobs.helpers import _fmt_dt, _job_has_running_run
from app.api.jobs.schemas import JobRunOut, JobRunsPageOut, JobTriggerOut, JobTriggerRequest
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.job_run import JobRun
from app.models.user import User
from app.services.scheduler_config import JOB_IDS
from app.services.scheduler_runtime import (
    release_manual_trigger,
    resolve_job_callable,
    try_acquire_manual_trigger,
)

router = APIRouter()
logger = logging.getLogger("zhange.jobs")


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
