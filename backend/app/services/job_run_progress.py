"""Shared run records and versioned progress snapshots for sync jobs."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.core.biz_logging import log_context
from app.core.database import SessionLocal
from app.core.timeutil import now_naive
from app.models.job_run import JobRun

SYNC_JOB_CATEGORIES: dict[str, str] = {
    "endfield_repo_sync": "repository",
    "arknights_repo_sync": "repository",
    "tarkov_overlay_repo_sync": "repository",
    "tarkov_svg_repo_sync": "repository",
    "arknights_catalog_sync": "data_pipeline",
    "game_schedule_arknights_sync": "data_pipeline",
    "game_schedule_endfield_sync": "data_pipeline",
    "tarkov_full_sync": "data_pipeline",
    "ror2_wiki_sync": "data_pipeline",
    "arknights_box_sync": "batch_sync",
    "ror2_weblate_sync": "asset_sync",
    "texteller_model_sync": "asset_sync",
}

_CATEGORY_LABELS = {
    "repository": "同步外部仓库",
    "data_pipeline": "采集并入库",
    "batch_sync": "批量同步对象",
    "asset_sync": "同步模型与译文",
}
_PHASE_LABELS = {
    "start": "准备同步",
    "check": "检查本地状态",
    "download": "下载数据",
    "persist": "写入数据",
    "overlay": "同步附加数据",
    "apply": "更新栏目",
    "done": "完成",
    "skip": "无需更新",
    "wait": "等待资源",
    "error": "执行失败",
}

_ACTIVE_RUN: ContextVar[tuple[str, int] | None] = ContextVar(
    "active_job_run", default=None
)


def category_for_job(job_key: str) -> str | None:
    return SYNC_JOB_CATEGORIES.get(job_key)


@contextmanager
def job_run_context(job_key: str, run_id: int) -> Iterator[None]:
    token = _ACTIVE_RUN.set((job_key, run_id))
    try:
        with log_context(job=job_key, job_run_id=run_id):
            yield
    finally:
        _ACTIVE_RUN.reset(token)


def active_job_run_id(job_key: str) -> int | None:
    active = _ACTIVE_RUN.get()
    return active[1] if active and active[0] == job_key else None


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def versioned_job_stats(
    job_key: str,
    *,
    status: str,
    stats: dict[str, Any] | None = None,
    message: str | None = None,
) -> dict[str, Any] | None:
    """Wrap a snapshot while retaining legacy fields at the top level."""
    category = category_for_job(job_key)
    if category is None:
        return stats

    raw = dict(stats or {})
    nested = raw.get("progress") if isinstance(raw.get("progress"), dict) else {}
    result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
    steps = raw.get("steps") if isinstance(raw.get("steps"), list) else None

    current = _as_number(nested.get("current"))
    total = _as_number(nested.get("total"))
    unit = nested.get("unit")
    if total is None or total <= 0:
        files_done = _as_number(raw.get("files_done"))
        files_total = _as_number(raw.get("files_total"))
        if files_done is not None and files_total is not None and files_total > 0:
            current, total, unit = files_done, files_total, "个文件"
        else:
            current_bytes = _as_number(raw.get("bytes"))
            total_bytes = _as_number(raw.get("total_bytes"))
            if (
                current_bytes is not None
                and total_bytes is not None
                and total_bytes > 0
            ):
                current, total, unit = current_bytes, total_bytes, "字节"

    progress: dict[str, Any] = {}
    if current is not None and total is not None and total > 0:
        progress = {
            "current": current,
            "total": total,
            "unit": str(unit or "项"),
            "percent": max(0, min(100, round(current * 100 / total))),
        }
    elif isinstance(nested, dict) and nested.get("percent") is not None:
        # Explicitly versioned progress can opt in by supplying known totals.
        if nested.get("reliable") is True:
            percent = _as_number(nested.get("percent"))
            if percent is not None:
                progress = {"percent": max(0, min(100, round(percent)))}

    phase = str(raw.get("phase") or "").strip()
    run_step_status = {
        "queued": "waiting",
        "running": "running",
        "ok": "success",
        "warning": "warning",
        "error": "error",
    }.get(status, "waiting")
    if not steps:
        label = _PHASE_LABELS.get(phase, _CATEGORY_LABELS[category])
        steps = [{"id": phase or "execute", "label": label, "status": run_step_status}]
    else:
        steps = [dict(step) for step in steps if isinstance(step, dict)]
        if status == "running" and not any(step.get("status") == "running" for step in steps):
            waiting_step = next(
                (step for step in steps if step.get("status") in {None, "waiting"}),
                None,
            )
            if waiting_step is not None:
                waiting_step["status"] = "running"
        elif status in {"ok", "warning", "error"}:
            changed = False
            for step in steps:
                if step.get("status") == "running":
                    step["status"] = run_step_status
                    changed = True
            if not changed:
                waiting_step = next(
                    (step for step in reversed(steps) if step.get("status") in {None, "waiting"}),
                    None,
                )
                if waiting_step is not None:
                    waiting_step["status"] = run_step_status

    safe_result = dict(result)
    counts = safe_result.get("counts")
    if not isinstance(counts, dict):
        count_keys = {
            "ok",
            "failed",
            "skipped",
            "total",
            "ok_count",
            "failed_count",
            "operator_count",
            "files_done",
            "files_total",
        }
        counts = {key: raw[key] for key in count_keys if key in raw and _as_number(raw[key]) is not None}
    if counts:
        safe_result["counts"] = counts
    if message and not message.lstrip().startswith(("{", "[")):
        safe_result.setdefault("summary", message[:500])

    # These protocol keys are rebuilt below. Keep task-specific legacy values
    # available for old readers and phased UI adapters.
    output = {
        key: value
        for key, value in raw.items()
        if key not in {"schema_version", "category", "steps", "progress", "result"}
    }
    output.update(
        {
            "schema_version": 1,
            "category": category,
            "steps": steps,
            "progress": progress,
            "result": safe_result,
        }
    )
    return output


def create_or_reuse_job_run(
    db: Session,
    job_key: str,
    *,
    message: str | None = None,
    stats: dict[str, Any] | None = None,
) -> JobRun:
    """Scheduled runs create a row; manually triggered runs reuse their queued row."""
    run_id = active_job_run_id(job_key)
    job = db.get(JobRun, run_id) if run_id is not None else None
    if job is None:
        job = JobRun(job_key=job_key, status="running", started_at=now_naive())
        db.add(job)
    else:
        job.status = "running"
        job.finished_at = None
    if message is not None:
        job.message = message[:500]
    job.stats = versioned_job_stats(
        job_key, status="running", stats=stats, message=message
    )
    return job


def write_job_run(
    run_id: int,
    job_key: str,
    *,
    status: str | None = None,
    message: str | None = None,
    stats: dict[str, Any] | None = None,
    finished: bool = False,
) -> None:
    db = SessionLocal()
    try:
        row = db.get(JobRun, run_id)
        if row is None:
            return
        if message is not None:
            row.message = message[:500]
        if status is not None:
            row.status = status
        if stats is not None or status is not None:
            row.stats = versioned_job_stats(
                job_key,
                status=status or row.status,
                stats=stats if stats is not None else row.stats,
                message=message if message is not None else row.message,
            )
        if finished:
            row.finished_at = now_naive()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_manual_job_run(run_id: int, job_key: str) -> None:
    write_job_run(
        run_id,
        job_key,
        status="running",
        message="正在启动任务",
        stats={"phase": "start"},
    )


def finish_manual_job_run(run_id: int, job_key: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(JobRun, run_id)
        if row is None or row.status not in {"queued", "running"}:
            return
        row.status = "ok"
        if not row.message or row.message.startswith("正在") or row.message == "等待执行":
            row.message = "执行完成"
        row.stats = versioned_job_stats(
            job_key,
            status="ok",
            stats=row.stats,
            message=row.message,
        )
        row.finished_at = now_naive()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_queued_job_run(db: Session, job_key: str, category: str) -> JobRun:
    message = "等待执行"
    run = JobRun(
        job_key=job_key,
        status="queued",
        message=message,
        started_at=now_naive(),
        stats={
            "schema_version": 1,
            "category": category,
            "steps": [{"id": "execute", "label": "等待任务启动", "status": "waiting"}],
            "progress": {},
            "result": {},
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
