"""清理过期 job_runs 与 checkin_logs（默认保留 90 天）。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timeutil import now_naive
from app.models.job_run import JobRun
from app.services.scheduler_config import load_scheduler_config

logger = logging.getLogger("zhange.job_runs_prune")

JOB_KEY = "job_runs_prune"
DEFAULT_RETENTION_DAYS = 90

_CHECKIN_LOG_MODELS: tuple[tuple[str, str], ...] = (
    ("skland", "app.models.skland.SklandCheckinLog"),
    ("taygedo", "app.models.taygedo.TaygedoCheckinLog"),
    ("exilium", "app.models.exilium.ExiliumCheckinLog"),
    ("kujiequ", "app.models.kujiequ.KujiequCheckinLog"),
)


def _retention_days(db: Session) -> int:
    cfg = load_scheduler_config(db)
    raw = (cfg.get(JOB_KEY) or {}).get("retention_days", DEFAULT_RETENTION_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_RETENTION_DAYS
    return max(7, min(3650, days))


def _import_log_model(dotted: str) -> Any:
    module_path, name = dotted.rsplit(".", 1)
    mod = __import__(module_path, fromlist=[name])
    return getattr(mod, name)


def prune_checkin_logs(db: Session, *, retention_days: int) -> dict[str, int]:
    cutoff = now_naive().date() - timedelta(days=retention_days)
    deleted: dict[str, int] = {}
    for platform, dotted in _CHECKIN_LOG_MODELS:
        model = _import_log_model(dotted)
        n = (
            db.query(model)
            .filter(model.checkin_date < cutoff)
            .delete(synchronize_session=False)
        )
        deleted[platform] = int(n)
    db.flush()
    return deleted


def prune_job_runs(
    db: Session,
    *,
    retention_days: int | None = None,
    keep_run_id: int | None = None,
) -> dict[str, Any]:
    days = retention_days if retention_days is not None else _retention_days(db)
    cutoff = now_naive() - timedelta(days=days)
    q = db.query(JobRun).filter(JobRun.started_at < cutoff)
    if keep_run_id is not None:
        q = q.filter(JobRun.id != keep_run_id)
    job_deleted = q.delete(synchronize_session=False)
    db.flush()
    checkin_deleted = prune_checkin_logs(db, retention_days=days)
    return {
        "deleted": int(job_deleted),
        "retention_days": days,
        "checkin_logs_deleted": checkin_deleted,
        "checkin_logs_total": sum(checkin_deleted.values()),
    }


def prune_job_wrapper() -> None:
    db = SessionLocal()
    run = JobRun(
        job_key=JOB_KEY,
        status="running",
        message="清理过期任务日志与签到日志",
        started_at=now_naive(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        stats = prune_job_runs(db, keep_run_id=run.id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("job_runs prune failed")
        db.rollback()
        run = db.get(JobRun, run.id)
        if run is not None:
            run.status = "error"
            run.message = str(exc)[:500]
            run.finished_at = now_naive()
            db.commit()
    else:
        run.status = "ok"
        run.message = (
            f"已删除 {stats['deleted']} 条 job_runs、"
            f"{stats['checkin_logs_total']} 条 checkin_logs"
            f"（保留 {stats['retention_days']} 天）"
        )
        run.stats = stats
        run.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
