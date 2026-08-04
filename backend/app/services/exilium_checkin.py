"""追放社区绑定与每日签到编排。"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.exilium import ExiliumBind, ExiliumCheckinLog
from app.models.job_run import JobRun
from app.models.member import Member
from app.services.checkin_common import (
    day_results_payload,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
    upsert_day_checkin_logs,
)
from app.services.exilium_client import (
    ExiliumApiError,
    ExiliumCredentials,
    checkin,
    ensure_session,
    exchange_item,
    friendly_error_message,
    get_user_score,
    list_exchange_items,
    list_score_logs,
    login_with_password,
    login_with_sms,
    mask_account,
    query_today,
)

logger = logging.getLogger(__name__)

JOB_KEY = "exilium_checkin"
_job_lock = threading.Lock()


def get_bind_for_member(db: Session, member_id: int) -> ExiliumBind | None:
    return db.query(ExiliumBind).filter(ExiliumBind.member_id == member_id).one_or_none()


def _load_creds(bind: ExiliumBind) -> ExiliumCredentials:
    raw = decrypt_secret(bind.credentials_enc)
    if not raw:
        raise ExiliumApiError("凭证已损坏，请重新绑定")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExiliumApiError("凭证格式无效，请重新绑定") from exc
    if not isinstance(payload, dict):
        raise ExiliumApiError("凭证格式无效，请重新绑定")
    return ExiliumCredentials.from_dict(payload)


def _save_creds(bind: ExiliumBind, creds: ExiliumCredentials) -> None:
    bind.credentials_enc = encrypt_secret(json.dumps(creds.to_dict(), ensure_ascii=False))
    bind.phone_mask = mask_account(creds.account_name) or creds.nickname
    bind.updated_at = now_naive()


def bind_with_password(db: Session, member: Member, account: str, password: str) -> ExiliumBind:
    creds = login_with_password(account, password)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = ExiliumBind(member_id=member.id, credentials_enc="", auto_checkin=True)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def bind_with_sms(db: Session, member: Member, phone: str, captcha: str) -> ExiliumBind:
    creds = login_with_sms(phone, captcha)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = ExiliumBind(member_id=member.id, credentials_enc="", auto_checkin=True)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def _maybe_checkin_after_bind(db: Session, bind: ExiliumBind) -> None:
    """绑定成功后：若开启自动签到且今日尚未签到，则立即补签。"""
    if not bind.auto_checkin:
        return
    try:
        run_checkin_for_bind(db, bind, force=False)
    except Exception:  # noqa: BLE001
        logger.exception(
            "exilium checkin after bind failed member_id=%s", bind.member_id
        )
        db.rollback()
        db.refresh(bind)


def unbind_exilium(db: Session, member: Member) -> None:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return
    db.delete(bind)
    db.commit()


def set_auto_checkin(db: Session, member: Member, enabled: bool) -> ExiliumBind:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    bind.auto_checkin = bool(enabled)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    return bind


def _session_for_bind(db: Session, bind: ExiliumBind) -> ExiliumCredentials:
    creds = _load_creds(bind)
    working = ensure_session(creds)
    if (
        working.token != creds.token
        or working.nickname != creds.nickname
        or working.user_id != creds.user_id
        or working.password != creds.password
    ):
        _save_creds(bind, working)
        db.commit()
    return working


def preview_roles(db: Session, member: Member) -> list[dict[str, str]]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    working = _session_for_bind(db, bind)
    return [
        {
            "game_code": "exilium_bbs",
            "game_name": "追放社区",
            "uid": working.user_id or working.account_name or "-",
            "role_name": working.nickname
            or mask_account(working.account_name)
            or "社区账号",
            "channel_name": "官方社区",
        }
    ]


def fetch_exchange_shop(db: Session, member: Member) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    working = _session_for_bind(db, bind)
    items = list_exchange_items(working)
    score = get_user_score(working)
    return {
        "score": score,
        "items": [item.to_dict() for item in items],
    }


def run_exchange_for_member(
    db: Session, member: Member, exchange_id: int
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    working = _session_for_bind(db, bind)
    shop_before = {i.exchange_id: i for i in list_exchange_items(working)}
    target = shop_before.get(int(exchange_id))
    if target is None:
        raise ExiliumApiError("兑换物品不存在或已下架")
    if (
        target.max_exchange_count > 0
        and target.exchange_count >= target.max_exchange_count
    ):
        raise ExiliumApiError("已达兑换上限")
    score_before = get_user_score(working)
    if score_before < target.use_score:
        raise ExiliumApiError(f"积分不足（需要 {target.use_score}，当前 {score_before}）")

    exchange_item(working, int(exchange_id))
    score_after = get_user_score(working)
    return {
        "ok": True,
        "message": f"已兑换 {target.item_name}*{target.item_count}，请到游戏邮箱领取",
        "score": score_after,
        "item": target.to_dict(),
    }


def fetch_score_logs(
    db: Session,
    member: Member,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    working = _session_for_bind(db, bind)
    return list_score_logs(working, page=page, page_size=page_size)


def query_today_for_bind(
    db: Session, bind: ExiliumBind, *, force: bool = False
) -> dict[str, Any]:
    checkin_date = today()
    if not force:
        cached = load_day_checkin_results(
            db,
            ExiliumCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
        )
        if cached is not None:
            return day_results_payload(cached)

    creds = _load_creds(bind)
    try:
        working, results = query_today(creds)
    except ExiliumApiError as exc:
        raise ExiliumApiError(friendly_error_message(exc.message)) from exc
    _save_creds(bind, working)
    now = now_naive()
    if results:
        upsert_day_checkin_logs(
            db,
            ExiliumCheckinLog,
            member_id=bind.member_id,
            bind_id=bind.id,
            checkin_date=checkin_date,
            results=results,
            now=now,
        )
    db.commit()
    return day_results_payload(results)


def run_checkin_for_bind(
    db: Session,
    bind: ExiliumBind,
    *,
    force: bool = False,
) -> dict[str, Any]:
    checkin_date = today()
    # 即使今日已签，仍走 checkin：会补跑每日任务（浏览/点赞/分享）
    creds = _load_creds(bind)
    try:
        working, result = checkin(creds, force=force)
    except ExiliumApiError as exc:
        raise ExiliumApiError(friendly_error_message(exc.message)) from exc

    _save_creds(bind, working)
    results = [result]
    ok, summary = summarize_results(results, empty_message="未执行签到")
    if result.extra_text:
        summary = f"{summary}\n{result.extra_text}"
    already_done = (
        not force
        and bind.last_checkin_date == checkin_date
        and bind.last_checkin_ok
        and result.status == "already"
    )
    now = now_naive()
    bind.last_checkin_at = now
    bind.last_checkin_date = checkin_date
    bind.last_checkin_ok = ok
    bind.last_checkin_summary = summary
    bind.updated_at = now
    upsert_day_checkin_logs(
        db,
        ExiliumCheckinLog,
        member_id=bind.member_id,
        bind_id=bind.id,
        checkin_date=checkin_date,
        results=results,
        now=now,
    )
    db.commit()

    return {
        "skipped": bool(already_done),
        "ok": ok,
        "summary": summary,
        "results": results_to_api(results),
    }


def run_checkin_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    return run_checkin_for_bind(db, bind, force=force)


def run_exilium_checkin_job(db: Session) -> dict[str, Any]:
    binds = (
        db.query(ExiliumBind)
        .options(joinedload(ExiliumBind.member))
        .filter(ExiliumBind.auto_checkin.is_(True))
        .all()
    )
    stats: dict[str, Any] = {"total": len(binds), "ok": 0, "failed": 0, "skipped": 0}
    for bind in binds:
        try:
            out = run_checkin_for_bind(db, bind, force=False)
            if out.get("skipped"):
                stats["skipped"] += 1
            elif out.get("ok"):
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("exilium auto checkin failed member_id=%s", bind.member_id)
            stats["failed"] += 1
            db.rollback()
    return stats


def checkin_job_wrapper() -> None:
    from app.core.database import SessionLocal

    if not _job_lock.acquire(blocking=False):
        logger.info("exilium checkin job already running, skip")
        return
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        stats = run_exilium_checkin_job(db)
        job.status = "ok"
        job.message = (
            f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
            f"跳过 {stats['skipped']}（共 {stats['total']}）"
        )
        job.stats = stats
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("exilium checkin job crashed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
        _job_lock.release()
