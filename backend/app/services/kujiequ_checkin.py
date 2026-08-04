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
    day_results_payload,
    is_success_status,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
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
        bind = KujiequBind(member_id=member.id, credentials_enc="", auto_checkin=True)
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
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    bind.auto_checkin = bool(enabled)
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
    db.commit()
    return day_results_payload(merged)


def run_checkin_for_bind(
    db: Session,
    bind: KujiequBind,
    *,
    force: bool = False,
) -> dict[str, Any]:
    checkin_date = today()
    if not force and bind.last_checkin_date == checkin_date and bind.last_checkin_ok:
        try:
            live = query_today_for_bind(db, bind, force=False)
            api_results = live.get("results") or []
            if api_results and all(
                is_success_status(str(r.get("status"))) for r in api_results
            ):
                return {
                    "skipped": True,
                    "ok": True,
                    "reason": "today_done",
                    "summary": live.get("summary") or "今日已签到",
                    "results": api_results,
                }
        except KujiequApiError:
            pass

    creds = _load_creds(bind)
    try:
        working, results = run_all_checkins(creds)
    except KujiequApiError as exc:
        raise KujiequApiError(friendly_error_message(exc.message), code=exc.code) from exc

    _save_creds(bind, working)
    ok, summary = summarize_results(results, empty_message="未执行任何签到")
    now = now_naive()
    bind.last_checkin_at = now
    bind.last_checkin_date = checkin_date
    bind.last_checkin_ok = ok
    bind.last_checkin_summary = summary
    bind.updated_at = now
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


def checkin_job_wrapper() -> None:
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
        binds = (
            db.query(KujiequBind)
            .options(joinedload(KujiequBind.member))
            .filter(KujiequBind.auto_checkin.is_(True))
            .all()
        )
        ok_n = 0
        fail_n = 0
        for bind in binds:
            try:
                result = run_checkin_for_bind(db, bind, force=False)
                if result.get("ok") or result.get("skipped"):
                    ok_n += 1
                else:
                    fail_n += 1
            except Exception as exc:  # noqa: BLE001
                fail_n += 1
                logger.exception(
                    "kujiequ auto checkin failed member_id=%s: %s",
                    bind.member_id,
                    exc,
                )
                db.rollback()
        run.status = "ok" if fail_n == 0 else "error"
        run.message = f"完成 {ok_n}，失败 {fail_n}，共 {len(binds)}"
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
