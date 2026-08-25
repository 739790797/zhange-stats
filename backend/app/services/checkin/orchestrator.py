"""统一签到编排：今日 logs 缓存 → Adapter 查/签 → checkin_common 落库。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.biz_logging import log_context
from app.core.timeutil import now_naive, today
from app.models.job_run import JobRun
from app.services.checkin.adapter import (
    CheckinPlatformAdapter,
    SkipPolicy,
)
from app.services.checkin.common import (
    LOG_SOURCE_ACTION,
    LOG_SOURCE_STATUS,
    apply_bind_last_checkin,
    day_results_payload,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
    today_done_from_logs,
    upsert_and_reload_day_results,
)
from app.services.checkin.role_prefs import RoleKey, collect_checkin_job_targets

logger = logging.getLogger(__name__)

_job_locks: dict[str, threading.Lock] = {}


def _job_lock_for(platform: str) -> threading.Lock:
    lock = _job_locks.get(platform)
    if lock is None:
        lock = threading.Lock()
        _job_locks[platform] = lock
    return lock


def query_today_for_bind(
    adapter: CheckinPlatformAdapter,
    db: Session,
    bind: Any,
    *,
    force: bool = False,
) -> dict[str, Any]:
    checkin_date = today()
    if not force:
        cached = load_day_checkin_results(
            db,
            adapter.log_model,
            member_id=bind.member_id,
            checkin_date=checkin_date,
        )
        if cached is not None:
            prepared = adapter.prepare_cached_results(cached)
            if prepared is not None:
                return day_results_payload(prepared)

    try:
        session = adapter.load_session(db, bind)
        session, results = adapter.query_today_all(session)
    except adapter.api_error_cls as exc:
        adapter.reraise_api_error(exc)
        raise  # pragma: no cover — reraise always raises

    adapter.save_session(db, bind, session)
    results = adapter.normalize_results(results)
    now = now_naive()
    merged = adapter.normalize_results(
        upsert_and_reload_day_results(
            db,
            adapter.log_model,
            member_id=bind.member_id,
            bind_id=bind.id,
            checkin_date=checkin_date,
            results=results,
            now=now,
            source=LOG_SOURCE_STATUS,
        )
    )
    db.commit()
    return day_results_payload(merged)


def _exchanges_from_results(results: list[Any]) -> list[dict[str, Any]]:
    """从现场 CheckinResult 提取上游 HTTP 原文（不落库）。"""
    out: list[dict[str, Any]] = []
    for r in results:
        req = getattr(r, "upstream_request", None)
        resp = getattr(r, "upstream_response", None)
        if not req and not resp:
            continue
        out.append(
            {
                "game_code": str(getattr(r, "game_code", "") or ""),
                "role_uid": str(getattr(r, "role_uid", "") or ""),
                "status": str(getattr(r, "status", "") or ""),
                "upstream_request": req,
                "upstream_response": resp,
            }
        )
    return out


def run_checkin_for_bind(
    adapter: CheckinPlatformAdapter,
    db: Session,
    bind: Any,
    *,
    force: bool = False,
    role_keys: set[RoleKey] | None = None,
) -> dict[str, Any]:
    checkin_date = today()

    if adapter.skip_policy == SkipPolicy.LOGS_AUTHORITY and not force:
        done = today_done_from_logs(
            db,
            adapter.log_model,
            member_id=bind.member_id,
            checkin_date=checkin_date,
            role_keys=role_keys,
        )
        if done is not None:
            full = load_day_checkin_results(
                db,
                adapter.log_model,
                member_id=bind.member_id,
                checkin_date=checkin_date,
            )
            payload = day_results_payload(full or done)
            return {
                "skipped": True,
                "ok": True,
                "reason": "today_done",
                "summary": payload.get("summary") or "今日已签到",
                "results": payload.get("results") or [],
                "exchanges": [],
            }

    try:
        session = adapter.load_session(db, bind)
        outcome = adapter.run_checkins(
            session, force=force, role_keys=role_keys
        )
    except adapter.api_error_cls as exc:
        adapter.reraise_api_error(exc)
        raise  # pragma: no cover

    if outcome.early_response is not None:
        early = dict(outcome.early_response)
        early.setdefault("exchanges", [])
        return early

    adapter.save_session(db, bind, outcome.session)
    results = adapter.normalize_results(outcome.results)
    exchanges = _exchanges_from_results(results)
    ok, summary = summarize_results(
        results, empty_message=adapter.empty_message
    )
    summary = adapter.enrich_summary(summary, results)
    skipped = adapter.mark_as_skipped(
        bind, results, force=force, checkin_date=checkin_date
    )
    now = now_naive()
    apply_bind_last_checkin(
        bind, now=now, checkin_date=checkin_date, ok=ok, summary=summary
    )
    merged = adapter.normalize_results(
        upsert_and_reload_day_results(
            db,
            adapter.log_model,
            member_id=bind.member_id,
            bind_id=bind.id,
            checkin_date=checkin_date,
            results=results,
            now=now,
            source=LOG_SOURCE_ACTION,
        )
    )
    adapter.after_checkin(db, bind, results)
    db.commit()
    return {
        "skipped": bool(skipped),
        "ok": ok,
        "summary": summary,
        "results": results_to_api(merged),
        "exchanges": exchanges,
    }


def run_checkin_job(
    adapter: CheckinPlatformAdapter,
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    targets = collect_checkin_job_targets(
        db,
        platform=adapter.platform,
        bind_model=adapter.bind_model,
        due_only=due_only,
        member_id=member_id,
    )
    binds_by_member = {
        b.member_id: b
        for b in db.query(adapter.bind_model)
        .options(joinedload(adapter.bind_model.member))
        .filter(adapter.bind_model.member_id.in_(list(targets.keys()) or [-1]))
        .all()
    }
    stats: dict[str, Any] = {
        "total": len(targets),
        "ok": 0,
        "failed": 0,
        "skipped": 0,
    }
    for mid, keys in targets.items():
        bind = binds_by_member.get(mid)
        if bind is None:
            continue
        if keys is not None and len(keys) == 0:
            stats["skipped"] += 1
            continue
        try:
            out = run_checkin_for_bind(
                adapter, db, bind, force=False, role_keys=keys
            )
            if out.get("skipped"):
                stats["skipped"] += 1
            elif out.get("ok"):
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "%s auto checkin failed member_id=%s",
                adapter.platform,
                mid,
            )
            stats["failed"] += 1
            db.rollback()
    return stats


def checkin_job_wrapper(
    adapter: CheckinPlatformAdapter,
    *,
    due_only: bool = True,
    member_id: int | None = None,
) -> None:
    from app.core.database import SessionLocal

    lock = _job_lock_for(adapter.platform)
    if not lock.acquire(blocking=False):
        logger.info("%s checkin job already running, skip", adapter.platform)
        return
    db = SessionLocal()
    job = JobRun(job_key=adapter.job_key, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    ctx_kwargs: dict[str, str | int | None] = {
        "platform": adapter.platform,
        "job": "checkin",
    }
    if member_id is not None:
        ctx_kwargs["member_id"] = member_id
    with log_context(**ctx_kwargs):
        try:
            logger.info(
                "%s checkin job begin due_only=%s member_id=%s",
                adapter.platform,
                due_only,
                member_id,
            )
            stats = run_checkin_job(
                adapter, db, due_only=due_only, member_id=member_id
            )
            logger.info(
                "%s checkin job done ok=%s failed=%s skipped=%s total=%s",
                adapter.platform,
                stats["ok"],
                stats["failed"],
                stats["skipped"],
                stats["total"],
            )
            job.status = "ok"
            job.message = (
                f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
                f"跳过 {stats['skipped']}（共 {stats['total']}）"
            )
            job.stats = stats
            job.finished_at = now_naive()
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s checkin job crashed", adapter.platform)
            job.status = "error"
            job.message = str(exc)
            job.finished_at = now_naive()
            db.commit()
        finally:
            db.close()
            lock.release()
