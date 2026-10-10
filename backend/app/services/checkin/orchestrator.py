"""统一签到编排：今日 logs 缓存 → Adapter 查/签 → checkin_common 落库。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy.orm import Session, joinedload

from app.core.biz_logging import clear_log_until_change, log_context, log_until_change
from app.core.timeutil import now as now_beijing
from app.core.timeutil import now_naive, today
from app.models.job_run import JobRun
from app.services.checkin.adapter import (
    CheckinPlatformAdapter,
    SkipPolicy,
)
from app.services.checkin.attempts import (
    classify_terminal_failure,
    record_checkin_attempt,
    record_checkin_outcome,
)
from app.services.checkin.common import (
    LOG_SOURCE_ACTION,
    LOG_SOURCE_STATUS,
    day_results_payload,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
    today_done_from_logs,
    upsert_and_reload_day_results,
)
from app.services.checkin.role_prefs import RoleKey, collect_checkin_job_targets

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_job_locks: dict[str, threading.Lock] = {}


def _job_lock_for(platform: str) -> threading.Lock:
    lock = _job_locks.get(platform)
    if lock is None:
        lock = threading.Lock()
        _job_locks[platform] = lock
    return lock


def _call_upstream(
    adapter: CheckinPlatformAdapter,
    db: Session,
    bind: Any,
    call: Callable[[Any], _T],
) -> _T:
    """load_session → 交还连接 → 打上游；Adapter 作废了失效凭证时换票重试一次。

    失败统一经 reraise_api_error 转成友好文案（含换票本身失败）。
    """
    try:
        session = adapter.load_session(db, bind)
        # 结束当前事务，把连接还给池，再打上游
        db.commit()
        try:
            return call(session)
        except adapter.api_error_cls as exc:
            if not adapter.renew_session_after_auth_error(db, bind, exc):
                raise
        session = adapter.load_session(db, bind)
        db.commit()
        return call(session)
    except adapter.api_error_cls as exc:
        adapter.reraise_api_error(exc)
        raise  # pragma: no cover — reraise always raises


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

    session, results = _call_upstream(adapter, db, bind, adapter.query_today_all)

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

    outcome = _call_upstream(
        adapter,
        db,
        bind,
        lambda session: adapter.run_checkins(
            session, force=force, role_keys=role_keys
        ),
    )

    if outcome.early_response is not None:
        # 探测目标时可能已换票（轮换型 refresh token），不写回下次就拿作废的旧票
        adapter.save_session(db, bind, outcome.session)
        db.commit()
        early = dict(outcome.early_response)
        early.setdefault("exchanges", [])
        early.setdefault(
            "no_targets", not early.get("skipped") and not early.get("results")
        )
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
        "no_targets": not results,
    }


def run_checkin_job(
    adapter: CheckinPlatformAdapter,
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
    targets: dict[int, set[RoleKey] | None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """due_only 时每个成员的结果记入当日重试账（checkin.attempts）。"""
    t = now or now_beijing()
    if targets is None:
        targets = collect_checkin_job_targets(
            db,
            platform=adapter.platform,
            bind_model=adapter.bind_model,
            due_only=due_only,
            member_id=member_id,
            log_model=adapter.log_model,
            now=t,
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
        log_key = f"checkin-auto:{adapter.platform}:{mid}"
        try:
            out = run_checkin_for_bind(
                adapter, db, bind, force=False, role_keys=keys
            )
        except adapter.api_error_cls as exc:
            db.rollback()
            stats["failed"] += 1
            message = getattr(exc, "message", None) or str(exc)
            log_until_change(
                logger,
                log_key,
                "%s auto checkin failed member_id=%s: %s",
                adapter.platform,
                mid,
                message,
            )
            if due_only:
                record_checkin_attempt(
                    adapter.platform,
                    mid,
                    keys,
                    now=t,
                    terminal=classify_terminal_failure([message]),
                )
            continue
        except Exception:  # noqa: BLE001
            db.rollback()
            stats["failed"] += 1
            logger.exception(
                "%s auto checkin crashed member_id=%s",
                adapter.platform,
                mid,
            )
            if due_only:
                record_checkin_attempt(adapter.platform, mid, keys, now=t)
            continue
        if due_only:
            record_checkin_outcome(adapter.platform, mid, keys, out, now=t)
        if out.get("skipped"):
            stats["skipped"] += 1
        elif out.get("ok"):
            stats["ok"] += 1
            clear_log_until_change(log_key)
        else:
            stats["failed"] += 1
    return stats


def checkin_job_wrapper(
    adapter: CheckinPlatformAdapter,
    *,
    due_only: bool = True,
    member_id: int | None = None,
) -> None:
    from app.core.database import SessionLocal
    from app.services.job_runs_prune import fail_job_run

    lock = _job_lock_for(adapter.platform)
    if not lock.acquire(blocking=False):
        log_until_change(
            logger,
            f"checkin-lock:{adapter.platform}",
            "%s checkin job already running, skip",
            adapter.platform,
        )
        return
    clear_log_until_change(f"checkin-lock:{adapter.platform}")
    # 连接池耗尽会在 SessionLocal / 首次 commit 抛出。锁必须在这次失败后仍释放，
    # 否则下一分钟 acquire 失败，签到会一直停。
    db: Session | None = None
    try:
        db = SessionLocal()
        t = now_beijing()
        targets = collect_checkin_job_targets(
            db,
            platform=adapter.platform,
            bind_model=adapter.bind_model,
            due_only=due_only,
            member_id=member_id,
            log_model=adapter.log_model,
            now=t,
        )
        if due_only and not targets:
            # 每分钟巡检多数时候没人到点：不写 JobRun，也不打 INFO
            logger.debug("%s checkin job idle", adapter.platform)
            clear_log_until_change(f"checkin-db:{adapter.platform}")
            return
        job = JobRun(job_key=adapter.job_key, status="running", started_at=now_naive())
        db.add(job)
        db.commit()
        run_id = job.id
        ctx_kwargs: dict[str, str | int | None] = {
            "platform": adapter.platform,
            "job": "checkin",
        }
        if member_id is not None:
            ctx_kwargs["member_id"] = member_id
        with log_context(**ctx_kwargs):
            try:
                stats = run_checkin_job(
                    adapter,
                    db,
                    due_only=due_only,
                    member_id=member_id,
                    targets=targets,
                    now=t,
                )
                logger.info(
                    "%s checkin job done ok=%s failed=%s skipped=%s total=%s",
                    adapter.platform,
                    stats["ok"],
                    stats["failed"],
                    stats["skipped"],
                    stats["total"],
                )
                failed = int(stats.get("failed") or 0)
                job.status = "error" if failed > 0 else "ok"
                job.message = (
                    f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
                    f"跳过 {stats['skipped']}（共 {stats['total']}）"
                )
                job.stats = stats
                job.finished_at = now_naive()
                db.commit()
                clear_log_until_change(f"checkin-db:{adapter.platform}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("%s checkin job crashed", adapter.platform)
                fail_job_run(db, run_id, str(exc))
                clear_log_until_change(f"checkin-db:{adapter.platform}")
    except Exception:
        log_until_change(
            logger,
            f"checkin-db:{adapter.platform}",
            "%s checkin job could not record run",
            adapter.platform,
            exc_info=True,
        )
    finally:
        try:
            if db is not None:
                db.close()
        finally:
            lock.release()
