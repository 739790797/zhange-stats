"""库街区绑定与每日签到编排（社区 + 鸣潮/战双）。"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.job_run import JobRun
from app.models.kujiequ import KujiequBind, KujiequCheckinLog
from app.models.member import Member
from app.services.checkin_common import (
    apply_bind_last_checkin,
    day_results_payload,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
    today_done_from_logs,
    upsert_and_reload_day_results,
)
from app.services.kujiequ_client import (
    KujiequApiError,
    KujiequCredentials,
    friendly_error_message,
    list_all_game_roles,
    login_with_sms,
    login_with_token,
    mask_phone,
    query_today_all,
    run_all_checkins,
)

logger = logging.getLogger(__name__)

JOB_KEY = "kujiequ_checkin"
_job_lock = threading.Lock()


def get_bind_for_member(db: Session, member_id: int) -> KujiequBind | None:
    return db.query(KujiequBind).filter(KujiequBind.member_id == member_id).one_or_none()


def _load_creds(bind: KujiequBind) -> KujiequCredentials:
    raw = decrypt_secret(bind.credentials_enc)
    if not raw:
        raise KujiequApiError("凭证已损坏，请重新绑定")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KujiequApiError("凭证格式无效，请重新绑定") from exc
    if not isinstance(payload, dict):
        raise KujiequApiError("凭证格式无效，请重新绑定")
    return KujiequCredentials.from_dict(payload)


def _save_creds(bind: KujiequBind, creds: KujiequCredentials) -> None:
    bind.credentials_enc = encrypt_secret(json.dumps(creds.to_dict(), ensure_ascii=False))
    bind.phone_mask = mask_phone(creds.phone) or (
        creds.user_name and f"@{creds.user_name}"
    ) or None
    bind.updated_at = now_naive()


def _upsert_bind(db: Session, member: Member, creds: KujiequCredentials) -> KujiequBind:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = KujiequBind(member_id=member.id, credentials_enc="", auto_checkin=False)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def bind_with_token(db: Session, member: Member, token: str) -> KujiequBind:
    creds = login_with_token(token)
    try:
        list_all_game_roles(creds)
    except KujiequApiError:
        pass
    return _upsert_bind(db, member, creds)


def bind_with_sms(db: Session, member: Member, phone: str, captcha: str) -> KujiequBind:
    creds = login_with_sms(phone, captcha)
    try:
        list_all_game_roles(creds)
    except KujiequApiError:
        pass
    return _upsert_bind(db, member, creds)


def _maybe_checkin_after_bind(db: Session, bind: KujiequBind) -> None:
    if not bind.auto_checkin:
        return
    try:
        run_checkin_for_bind(db, bind, force=False)
    except Exception:  # noqa: BLE001
        logger.exception("kujiequ checkin after bind failed member_id=%s", bind.member_id)
        db.rollback()
        db.refresh(bind)


def unbind_kujiequ(db: Session, member: Member) -> None:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return
    db.delete(bind)
    db.commit()


def set_auto_checkin(db: Session, member: Member, enabled: bool) -> KujiequBind:
    return update_bind_prefs(db, member, auto_checkin=bool(enabled))


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> KujiequBind:
    from app.services.checkin_schedule import clamp_checkin_hour, clamp_checkin_minute

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    if auto_checkin is not None:
        bind.auto_checkin = bool(auto_checkin)
    if checkin_hour is not None:
        bind.checkin_hour = clamp_checkin_hour(checkin_hour)
    if checkin_minute is not None:
        bind.checkin_minute = clamp_checkin_minute(checkin_minute)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    return bind


def preview_roles(db: Session, member: Member) -> list[dict[str, str]]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    creds = _load_creds(bind)
    roles = list_all_game_roles(creds)
    return [
        {
            "game_code": f"game_{r.game_id}",
            "game_name": r.game_name,
            "uid": r.role_id,
            "role_name": r.role_name,
            "channel_name": r.server_name,
        }
        for r in roles
    ]


def query_today_for_bind(
    db: Session, bind: KujiequBind, *, force: bool = False
) -> dict[str, Any]:
    checkin_date = today()
    if not force:
        cached = load_day_checkin_results(
            db,
            KujiequCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
        )
        if cached is not None:
            return day_results_payload(cached)

    creds = _load_creds(bind)
    try:
        working, results = query_today_all(creds)
    except KujiequApiError as exc:
        raise KujiequApiError(friendly_error_message(exc.message), code=exc.code) from exc
    _save_creds(bind, working)
    now = now_naive()
    merged = upsert_and_reload_day_results(
        db,
        KujiequCheckinLog,
        member_id=bind.member_id,
        bind_id=bind.id,
        checkin_date=checkin_date,
        results=results,
        now=now,
    )
    # 同步官方后刷新汇总，避免「我的日常」仍显示过期的「请求成功」
    ok, summary = summarize_results(merged, empty_message="未找到可签到目标")
    apply_bind_last_checkin(
        bind, now=now, checkin_date=checkin_date, ok=ok, summary=summary
    )
    db.commit()
    return day_results_payload(merged)


def run_checkin_for_bind(
    db: Session,
    bind: KujiequBind,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    checkin_date = today()
    if not force:
        done = today_done_from_logs(
            db,
            KujiequCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
            role_keys=role_keys,
        )
        if done is not None:
            full = load_day_checkin_results(
                db,
                KujiequCheckinLog,
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
            }

    creds = _load_creds(bind)
    try:
        working, results = run_all_checkins(creds, role_keys=role_keys)
    except KujiequApiError as exc:
        raise KujiequApiError(friendly_error_message(exc.message), code=exc.code) from exc

    _save_creds(bind, working)
    ok, summary = summarize_results(results, empty_message="未执行任何签到")
    now = now_naive()
    apply_bind_last_checkin(
        bind, now=now, checkin_date=checkin_date, ok=ok, summary=summary
    )
    merged = upsert_and_reload_day_results(
        db,
        KujiequCheckinLog,
        member_id=bind.member_id,
        bind_id=bind.id,
        checkin_date=checkin_date,
        results=results,
        now=now,
    )
    db.commit()
    return {
        "skipped": False,
        "ok": ok,
        "summary": summary,
        "results": results_to_api(merged),
    }


def run_checkin_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    return run_checkin_for_bind(db, bind, force=force)


def run_kujiequ_checkin_job(
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    from app.services.checkin_role_prefs import (
        PLATFORM_KUJIEQU,
        collect_checkin_job_targets,
    )

    targets = collect_checkin_job_targets(
        db,
        platform=PLATFORM_KUJIEQU,
        bind_model=KujiequBind,
        due_only=due_only,
        member_id=member_id,
    )
    binds_by_member = {
        b.member_id: b
        for b in db.query(KujiequBind)
        .options(joinedload(KujiequBind.member))
        .filter(KujiequBind.member_id.in_(list(targets.keys()) or [-1]))
        .all()
    }
    stats: dict[str, Any] = {"total": len(targets), "ok": 0, "failed": 0, "skipped": 0}
    for mid, role_keys in targets.items():
        bind = binds_by_member.get(mid)
        if bind is None:
            continue
        if role_keys is not None and len(role_keys) == 0:
            stats["skipped"] += 1
            continue
        try:
            result = run_checkin_for_bind(db, bind, force=False, role_keys=role_keys)
            if result.get("skipped"):
                stats["skipped"] += 1
            elif result.get("ok"):
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        except Exception:  # noqa: BLE001
            stats["failed"] += 1
            logger.exception(
                "kujiequ auto checkin failed member_id=%s",
                mid,
            )
            db.rollback()
    return stats


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    from app.core.database import SessionLocal

    if not _job_lock.acquire(blocking=False):
        logger.warning("kujiequ checkin job already running, skip")
        return
    db = SessionLocal()
    run = JobRun(job_key=JOB_KEY, status="running", message="库街区每日签到")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        stats = run_kujiequ_checkin_job(db, due_only=due_only, member_id=member_id)
        run.status = "ok" if stats["failed"] == 0 else "error"
        run.message = (
            f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
            f"跳过 {stats['skipped']}（共 {stats['total']}）"
        )
        run.stats = stats
        run.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("kujiequ checkin job failed: %s", exc)
        db.rollback()
        try:
            run.status = "error"
            run.message = str(exc)[:300]
            run.finished_at = now_naive()
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()
        _job_lock.release()
