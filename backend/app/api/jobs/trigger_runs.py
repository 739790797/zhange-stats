from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.jobs.catalog import JOB_CATALOG, _KNOWN_JOB_IDS
from app.api.jobs.helpers import _fmt_dt, _job_has_running_run
from app.api.jobs.schemas import (
    JobRunEventsOut,
    JobRunLogOut,
    JobRunOut,
    JobRunsPageOut,
    JobTriggerExchangeOut,
    JobTriggerOut,
    JobTriggerRequest,
)
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.user import User
from app.services.checkin.adapter import CheckinPlatformAdapter
from app.services.checkin.orchestrator import run_checkin_for_bind
from app.services.checkin.registry import get_checkin_adapters
from app.services.platform_features import PLATFORM_SHORT_NAMES
from app.services.job_run_progress import (
    category_for_job,
    create_queued_job_run,
    write_job_run,
)
from app.services.job_process_supervisor import launch_sync_job_process
from app.services.job_run_logs import list_job_run_logs
from app.services.scheduler_config import JOB_IDS
from app.services.scheduler_runtime import (
    CHECKIN_JOB_IDS,
    release_manual_trigger,
    resolve_job_callable,
    resolve_sync_job_handler,
    try_acquire_manual_trigger,
)

router = APIRouter()
logger = logging.getLogger("zhange.jobs")

_CHECKIN_JOB_SET = frozenset(CHECKIN_JOB_IDS)


def _checkin_adapter_for_job(job_id: str) -> CheckinPlatformAdapter | None:
    return next(
        (a for a in get_checkin_adapters().values() if a.job_key == job_id),
        None,
    )


def _run_sync_role_checkin(
    db: Session,
    *,
    job_id: str,
    member_id: int,
    game_code: str,
    role_uid: str,
) -> dict[str, Any]:
    """角色级同步签到（force），供管理端排障拿上游原文。"""
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    adapter = _checkin_adapter_for_job(job_id)
    if adapter is None:
        raise HTTPException(status_code=400, detail="该任务不支持角色级同步执行")
    bind = adapter.get_bind(db, member.id)
    if bind is None:
        name = PLATFORM_SHORT_NAMES.get(adapter.platform, adapter.platform)
        raise HTTPException(status_code=400, detail=f"该用户尚未绑定{name}")
    try:
        return run_checkin_for_bind(
            adapter, db, bind, force=True, role_keys={(game_code, role_uid)}
        )
    except adapter.api_error_cls as exc:
        msg = getattr(exc, "message", None) or str(exc)
        raise HTTPException(status_code=400, detail=msg) from exc


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
    game_code = (body.game_code or "").strip() if body else ""
    role_uid = (body.role_uid or "").strip() if body else ""

    if member_id is not None:
        meta = next((m for m in JOB_CATALOG if m["id"] == job_id), None)
        if not meta or meta.get("kind") != "user_schedule":
            raise HTTPException(
                status_code=400, detail="仅签到类任务支持按用户手动执行"
            )

    # 角色级：同步 force 签到，返回上游 HTTP 原文
    if (
        job_id in _CHECKIN_JOB_SET
        and member_id is not None
        and game_code
        and role_uid
    ):
        out = _run_sync_role_checkin(
            db,
            job_id=job_id,
            member_id=member_id,
            game_code=game_code,
            role_uid=role_uid,
        )
        exchanges = [
            JobTriggerExchangeOut(
                game_code=str(item.get("game_code") or ""),
                role_uid=str(item.get("role_uid") or ""),
                status=str(item.get("status") or ""),
                upstream_request=item.get("upstream_request"),
                upstream_response=item.get("upstream_response"),
            )
            for item in (out.get("exchanges") or [])
            if isinstance(item, dict)
        ]
        summary = str(out.get("summary") or "")
        ok = out.get("ok")
        return JobTriggerOut(
            accepted=True,
            job_id=job_id,
            message=summary or "执行完成",
            ok=bool(ok) if ok is not None else None,
            summary=summary or None,
            exchanges=exchanges,
        )

    if game_code or role_uid:
        raise HTTPException(
            status_code=400,
            detail="角色级执行需同时提供 member_id、game_code、role_uid",
        )

    if _job_has_running_run(db, job_id):
        raise HTTPException(status_code=409, detail="任务正在执行中，请稍后再试")

    if not try_acquire_manual_trigger(job_id):
        raise HTTPException(status_code=409, detail="任务正在执行中，请稍后再试")

    category = category_for_job(job_id)
    try:
        if category is not None:
            resolve_sync_job_handler(job_id, db)
            runner = None
        else:
            runner = resolve_job_callable(job_id, db, member_id=member_id)
    except KeyError:
        release_manual_trigger(job_id)
        raise HTTPException(status_code=404, detail="未知任务") from None
    except RuntimeError as exc:
        release_manual_trigger(job_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id: int | None = None
    if category is not None:
        try:
            run_id = int(create_queued_job_run(db, job_id, category).id)
        except Exception:
            release_manual_trigger(job_id)
            raise

        try:
            launch_sync_job_process(
                job_id,
                run_id,
                on_finish=lambda: release_manual_trigger(job_id),
            )
        except Exception as exc:  # noqa: BLE001
            release_manual_trigger(job_id)
            write_job_run(
                run_id,
                job_id,
                status="error",
                message="无法启动同步命令",
                stats={"phase": "error"},
                finished=True,
            )
            logger.exception("manual sync process launch failed job_id=%s", job_id)
            raise HTTPException(status_code=500, detail="无法启动同步任务") from exc

        return JobTriggerOut(
            accepted=True,
            job_id=job_id,
            run_id=run_id,
            category=category,
            message="已提交执行" if member_id is None else f"已提交用户 {member_id} 的执行",
        )

    def _run() -> None:
        try:
            assert runner is not None
            runner()
        except Exception as exc:  # noqa: BLE001
            logger.exception("manual trigger failed job_id=%s", job_id)
            if run_id is not None:
                try:
                    write_job_run(
                        run_id,
                        job_id,
                        status="error",
                        message=str(exc)[:500] or "任务执行失败",
                        stats={"phase": "error"},
                        finished=True,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "manual trigger run update failed job_id=%s run_id=%s",
                        job_id,
                        run_id,
                    )
        finally:
            release_manual_trigger(job_id)

    try:
        threading.Thread(
            target=_run,
            name=f"job-trigger-{job_id}",
            daemon=True,
        ).start()
    except Exception as exc:  # noqa: BLE001
        release_manual_trigger(job_id)
        if run_id is not None:
            write_job_run(
                run_id,
                job_id,
                status="error",
                message="无法启动后台任务",
                stats={"phase": "error"},
                finished=True,
            )
        raise HTTPException(status_code=500, detail="无法启动后台任务") from exc

    return JobTriggerOut(
        accepted=True,
        job_id=job_id,
        run_id=run_id,
        category=category,
        message="已提交执行" if member_id is None else f"已提交用户 {member_id} 的执行",
    )


@router.get("/jobs/{job_id}/runs", response_model=JobRunsPageOut)
def list_job_runs(
    job_id: str,
    run_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> JobRunsPageOut:
    if job_id not in _KNOWN_JOB_IDS and job_id not in JOB_IDS:
        raise HTTPException(status_code=404, detail="未知任务")

    query = db.query(JobRun).filter(JobRun.job_key == job_id)
    if run_id is not None:
        query = query.filter(JobRun.id == run_id)
    total = db.query(func.count(JobRun.id)).filter(JobRun.job_key == job_id)
    if run_id is not None:
        total = total.filter(JobRun.id == run_id)
    total_count = total.scalar() or 0
    rows = (
        query
        .order_by(desc(JobRun.started_at), desc(JobRun.id))
        .offset((page - 1) * page_size if run_id is None else 0)
        .limit(page_size if run_id is None else 1)
        .all()
    )
    items = [_job_run_out(row) for row in rows]
    return JobRunsPageOut(
        total=int(total_count),
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get(
    "/jobs/{job_id}/runs/{run_id}/events", response_model=JobRunEventsOut
)
def get_job_run_events(
    job_id: str,
    run_id: int,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> JobRunEventsOut:
    if job_id not in _KNOWN_JOB_IDS and job_id not in JOB_IDS:
        raise HTTPException(status_code=404, detail="未知任务")
    run = db.get(JobRun, run_id)
    if run is None or run.job_key != job_id:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    rows = list_job_run_logs(run_id, after_id=after_id, limit=limit + 1)
    has_more = len(rows) > limit
    selected = rows[:limit]
    return JobRunEventsOut(
        run=_job_run_out(run),
        logs=[
            JobRunLogOut(
                id=row.id,
                created_at=_fmt_dt(row.created_at) or "",
                level=row.level,
                logger=row.logger,
                message=row.message,
                is_truncation=row.is_truncation,
            )
            for row in selected
        ],
        next_after_id=selected[-1].id if selected else after_id,
        has_more=has_more,
    )
def _job_run_out(row: JobRun) -> JobRunOut:
    return JobRunOut(
        id=row.id,
        job_key=row.job_key,
        status=row.status,
        started_at=_fmt_dt(row.started_at),
        finished_at=_fmt_dt(row.finished_at),
        message=row.message,
        stats=row.stats,
        live_log=None,
    )
