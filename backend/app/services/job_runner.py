"""Shared sync-task dispatcher used by APScheduler and the CLI process."""

from __future__ import annotations

import logging
from typing import Callable

from app.core.biz_logging import wrap_scheduled_job
from app.core.database import SessionLocal
from app.models.job_run import JobRun
from app.services.job_execution_lock import (
    JobExecutionBusy,
    JobExecutionLockUnavailable,
    job_execution_lock,
)
from app.services.job_run_logs import JobRunLogCaptureHandler
from app.services.job_run_progress import (
    category_for_job,
    create_queued_job_run,
    finish_manual_job_run,
    job_run_context,
    start_manual_job_run,
    write_job_run,
)

logger = logging.getLogger("zhange.job_runner")


class SyncJobFailed(RuntimeError):
    """A sync handler finished with an error status or raised an exception."""


def _run_status(run_id: int) -> tuple[str | None, str | None]:
    db = SessionLocal()
    try:
        row = db.get(JobRun, run_id)
        return (row.status, row.message) if row is not None else (None, None)
    finally:
        db.close()


def _set_run_warning(run_id: int, job_id: str, message: str) -> None:
    write_job_run(
        run_id,
        job_id,
        status="warning",
        message=message,
        stats={"phase": "skip", "result": {"summary": message}},
        finished=True,
    )


def _set_run_error(run_id: int, job_id: str, message: str) -> None:
    write_job_run(
        run_id,
        job_id,
        status="error",
        message=message[:500] or "任务执行失败",
        stats={"phase": "error", "result": {"summary": message[:500]}},
        finished=True,
    )


def _create_run(job_id: str) -> int:
    category = category_for_job(job_id)
    if category is None:
        raise ValueError(f"任务不属于同步任务：{job_id}")
    db = SessionLocal()
    try:
        row = create_queued_job_run(db, job_id, category)
        return int(row.id)
    finally:
        db.close()


def execute_sync_job(
    job_id: str,
    handler: Callable[[], object],
    *,
    run_id: int | None = None,
    capture_logs: bool = False,
) -> tuple[int, str]:
    """Run one registered sync task under the shared lock and JobRun context.

    Scheduled jobs omit ``run_id`` and get their own record. Web CLI children
    receive the already-created queued run id from the trigger endpoint.
    """
    if category_for_job(job_id) is None:
        raise ValueError(f"任务不属于同步任务：{job_id}")
    run_id = run_id or _create_run(job_id)
    capture = JobRunLogCaptureHandler(run_id) if capture_logs else None
    root_logger = logging.getLogger()
    if capture is not None:
        root_logger.addHandler(capture)
    try:
        with job_execution_lock(job_id):
            with job_run_context(job_id, run_id):
                start_manual_job_run(run_id, job_id)
                try:
                    wrap_scheduled_job(job_id, handler)()
                except Exception as exc:  # noqa: BLE001
                    _set_run_error(run_id, job_id, str(exc) or "任务执行失败")
                    raise
                finish_manual_job_run(run_id, job_id)
                status, message = _run_status(run_id)
                if status == "error":
                    raise SyncJobFailed(message or "任务执行失败")
                return run_id, status or "ok"
    except JobExecutionBusy as exc:
        _set_run_warning(run_id, job_id, str(exc) or "任务正在执行")
        return run_id, "warning"
    except JobExecutionLockUnavailable as exc:
        _set_run_error(run_id, job_id, str(exc))
        raise
    finally:
        if capture is not None:
            try:
                capture.flush_to_store()
            except Exception:  # noqa: BLE001
                logger.exception("job log flush failed job_id=%s run_id=%s", job_id, run_id)
            root_logger.removeHandler(capture)


def scheduled_sync_job(job_id: str, handler: Callable[[], object]) -> None:
    """APScheduler adapter; logged failures remain visible to APScheduler."""
    try:
        execute_sync_job(job_id, handler, capture_logs=True)
    except Exception:
        logger.exception("scheduled sync job failed job_id=%s", job_id)
        raise
