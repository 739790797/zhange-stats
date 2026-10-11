"""清理过期 job_runs 与 checkin_logs（默认保留 90 天），维护 Minecraft 性能聚合档，删除超过 14 天的 RUM 样本与过期的验证码 / OAuth 换票。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timeutil import now_naive
from app.models.job_run import JobRun
from app.models.register_challenge import RegisterChallenge
from app.services.minecraft.perf_rollup import maintain_perf_archive
from app.services.oauth_ticket import prune_expired_oauth_tickets
from app.services.rum import prune_rum_samples
from app.services.scheduler_config import load_scheduler_config

logger = logging.getLogger("zhange.job_runs_prune")

JOB_KEY = "job_runs_prune"
DEFAULT_RETENTION_DAYS = 90
# 过期验证码多留一天再删：这期间提交旧码仍提示「已过期」，而不是「请先发送验证码」
CHALLENGE_PRUNE_GRACE = timedelta(days=1)

# 超过这个时长仍是 running 的行视为僵尸（线程已死却没回写），不再挡手动触发。
STALE_RUNNING_AFTER = timedelta(hours=6)


INTERRUPTED_MESSAGE = "进程重启，任务中断"


def fail_job_run(
    db: Session,
    run_id: int,
    message: str,
    *,
    stats: dict[str, Any] | None = None,
) -> None:
    """失败回写：先 rollback 再按 id 重读，否则会话卡在失败事务里 commit 不了，行会一直停在 running。"""
    db.rollback()
    run = db.get(JobRun, run_id)
    if run is None:
        return
    run.status = "error"
    run.message = message
    if stats is not None:
        run.stats = stats
    run.finished_at = now_naive()
    db.commit()


def mark_interrupted_job_runs(db: Session) -> int:
    """启动时把上个进程遗留的 running 记录收尾为 error（单副本部署：此刻不可能有任务在跑）。"""
    n = (
        db.query(JobRun)
        .filter(JobRun.status == "running")
        .update(
            {
                JobRun.status: "error",
                JobRun.finished_at: now_naive(),
                JobRun.message: INTERRUPTED_MESSAGE,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return int(n or 0)


def _retention_days(db: Session) -> int:
    cfg = load_scheduler_config(db)
    raw = (cfg.get(JOB_KEY) or {}).get("retention_days", DEFAULT_RETENTION_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_RETENTION_DAYS
    return max(7, min(3650, days))


def prune_checkin_logs(db: Session, *, retention_days: int) -> dict[str, int]:
    from app.services.checkin.registry import get_checkin_adapters

    cutoff = now_naive().date() - timedelta(days=retention_days)
    deleted: dict[str, int] = {}
    for platform, adapter in get_checkin_adapters().items():
        model = adapter.log_model
        n = (
            db.query(model)
            .filter(model.checkin_date < cutoff)
            .delete(synchronize_session=False)
        )
        deleted[platform] = int(n)
    db.flush()
    return deleted


def prune_expired_auth_rows(db: Session) -> dict[str, int]:
    challenges = (
        db.query(RegisterChallenge)
        .filter(RegisterChallenge.expires_at < now_naive() - CHALLENGE_PRUNE_GRACE)
        .delete(synchronize_session=False)
    )
    db.flush()
    return {
        "register_challenges": int(challenges),
        "oauth_exchange_tickets": prune_expired_oauth_tickets(db),
    }


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
    mc_perf = maintain_perf_archive(db, prune=True)
    rum_deleted = prune_rum_samples(db)
    auth_deleted = prune_expired_auth_rows(db)
    return {
        "deleted": int(job_deleted),
        "retention_days": days,
        "checkin_logs_deleted": checkin_deleted,
        "checkin_logs_total": sum(checkin_deleted.values()),
        "minecraft_perf": mc_perf,
        "rum_samples_deleted": rum_deleted,
        "auth_rows_deleted": auth_deleted,
    }


def prune_job_wrapper() -> None:
    db = SessionLocal()
    run = JobRun(
        job_key=JOB_KEY,
        status="running",
        message="清理过期任务日志、签到日志、RUM 样本，并上卷 Minecraft 性能档",
        started_at=now_naive(),
    )
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        stats = prune_job_runs(db, keep_run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("job_runs prune failed")
        fail_job_run(db, run_id, str(exc)[:500])
    else:
        auth = stats.get("auth_rows_deleted") or {}
        run.status = "ok"
        run.message = (
            f"已删除 {stats['deleted']} 条 job_runs、"
            f"{stats['checkin_logs_total']} 条 checkin_logs"
            f"（保留 {stats['retention_days']} 天）；"
            f"MC 原始采样删除 {stats.get('minecraft_perf', {}).get('raw_deleted', 0)} 条；"
            f"RUM 样本删除 {stats.get('rum_samples_deleted', 0)} 条；"
            f"过期验证码 {auth.get('register_challenges', 0)} 条、"
            f"OAuth 换票 {auth.get('oauth_exchange_tickets', 0)} 条"
        )
        run.stats = stats
        run.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
