"""塔吉多绑定与每日签到编排。"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.taygedo import TaygedoBind, TaygedoCheckinLog
from app.services.checkin_common import (
    CheckinResult,
    day_results_payload,
    is_success_status,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
    upsert_and_reload_day_results,
)
from app.services.taygedo_client import (
    TaygedoApiError,
    TaygedoCredentials,
    checkin_target,
    friendly_error_message,
    list_all_game_roles,
    login_with_password,
    login_with_sms,
    mask_phone,
    query_today_all,
    refresh_access_token,
)

logger = logging.getLogger(__name__)

JOB_KEY = "taygedo_checkin"
_job_lock = threading.Lock()


def get_bind_for_member(db: Session, member_id: int) -> TaygedoBind | None:
    return db.query(TaygedoBind).filter(TaygedoBind.member_id == member_id).one_or_none()


def _load_creds(bind: TaygedoBind) -> TaygedoCredentials:
    raw = decrypt_secret(bind.credentials_enc)
    if not raw:
        raise TaygedoApiError("凭证已损坏，请重新绑定")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TaygedoApiError("凭证格式无效，请重新绑定") from exc
    if not isinstance(payload, dict):
        raise TaygedoApiError("凭证格式无效，请重新绑定")
    return TaygedoCredentials.from_dict(payload)


def _save_creds(bind: TaygedoBind, creds: TaygedoCredentials) -> None:
    bind.credentials_enc = encrypt_secret(json.dumps(creds.to_dict(), ensure_ascii=False))
    bind.phone_mask = mask_phone(creds.phone)
    bind.updated_at = now_naive()


def bind_with_password(db: Session, member: Member, phone: str, password: str) -> TaygedoBind:
    creds = login_with_password(phone, password)
    try:
        list_all_game_roles(creds)
    except TaygedoApiError:
        pass

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = TaygedoBind(member_id=member.id, credentials_enc="", auto_checkin=True)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def bind_with_sms(
    db: Session, member: Member, phone: str, captcha: str, device_id: str
) -> TaygedoBind:
    creds = login_with_sms(phone, captcha, device_id)
    try:
        list_all_game_roles(creds)
    except TaygedoApiError:
        pass

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = TaygedoBind(member_id=member.id, credentials_enc="", auto_checkin=True)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def bind_with_credentials_json(db: Session, member: Member, raw_json: str) -> TaygedoBind:
    text = (raw_json or "").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TaygedoApiError("请粘贴合法的账号 JSON") from exc
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        raise TaygedoApiError("账号 JSON 格式无效")
    creds = TaygedoCredentials.from_dict(payload)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = TaygedoBind(member_id=member.id, credentials_enc="", auto_checkin=True)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def _maybe_checkin_after_bind(db: Session, bind: TaygedoBind) -> None:
    """绑定成功后：若开启自动签到且今日尚未签到，则立即补签。"""
    if not bind.auto_checkin:
        return
    try:
        run_checkin_for_bind(db, bind, force=False)
    except Exception:  # noqa: BLE001
        logger.exception(
            "taygedo checkin after bind failed member_id=%s", bind.member_id
        )
        db.rollback()
        db.refresh(bind)


def unbind_taygedo(db: Session, member: Member) -> None:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return
    db.delete(bind)
    db.commit()


def set_auto_checkin(db: Session, member: Member, enabled: bool) -> TaygedoBind:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
    bind.auto_checkin = bool(enabled)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    return bind


def preview_roles(db: Session, member: Member) -> list[dict[str, str]]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
    creds = _load_creds(bind)
    from app.services.taygedo_client import ensure_session

    working = ensure_session(creds)
    roles = list_all_game_roles(working)
    if working.access_token != creds.access_token or working.refresh_token != creds.refresh_token:
        _save_creds(bind, working)
        db.commit()

    out: list[dict[str, str]] = []
    for r in roles:
        out.append(
            {
                "game_code": r.game_code,
                "game_name": r.game_name,
                "uid": r.role_id,
                "role_name": r.role_name,
                "channel_name": r.game_name,
            }
        )
    return out


def _summarize(results: list[CheckinResult]) -> tuple[bool, str]:
    return summarize_results(results, empty_message="未执行任何签到")


def query_today_for_bind(
    db: Session, bind: TaygedoBind, *, force: bool = False
) -> dict[str, Any]:
    """今日签到状态：有今日日志则读库；否则查官方并落库。"""
    checkin_date = today()
    if not force:
        cached = load_day_checkin_results(
            db,
            TaygedoCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
        )
        if cached is not None:
            return day_results_payload(cached)

    creds = _load_creds(bind)
    try:
        working, results = query_today_all(creds)
    except TaygedoApiError as exc:
        raise TaygedoApiError(friendly_error_message(exc.message)) from exc
    _save_creds(bind, working)
    now = now_naive()
    merged = upsert_and_reload_day_results(
        db,
        TaygedoCheckinLog,
        member_id=bind.member_id,
        bind_id=bind.id,
        checkin_date=checkin_date,
        results=results,
        now=now,
    )
    db.commit()
    return day_results_payload(merged)


def query_today_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
    return query_today_for_bind(db, bind, force=force)


def run_checkin_for_bind(
    db: Session,
    bind: TaygedoBind,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """手动 / 自动签到：始终以官方为准；不写签到日志表。"""
    from app.services.taygedo_client import list_checkin_targets

    checkin_date = today()
    if (
        not force
        and bind.last_checkin_date == checkin_date
        and bind.last_checkin_ok
    ):
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
        except TaygedoApiError:
            pass

    creds = _load_creds(bind)
    working, targets = list_checkin_targets(creds)
    _save_creds(bind, working)

    if not targets:
        return {
            "skipped": False,
            "ok": False,
            "summary": "未找到可签到目标",
            "results": [],
        }

    # 先查官方今日状态；已签则跳过 POST（与森空岛一致）
    live_working, live_results = query_today_all(working)
    working = live_working
    live_map = {(r.game_code, r.role_uid): r for r in live_results}

    results: list[CheckinResult] = []
    for game_code, role in targets:
        role_uid = role.role_id if role else "-"
        probed = live_map.get((game_code, role_uid))
        if (
            not force
            and probed is not None
            and is_success_status(probed.status)
        ):
            results.append(probed)
            continue

        try:
            result = checkin_target(working, game_code=game_code, role=role)
        except TaygedoApiError as exc:
            if "登录" in (exc.message or "") or exc.code in (401, 402):
                try:
                    working = refresh_access_token(working)
                    result = checkin_target(working, game_code=game_code, role=role)
                except TaygedoApiError as exc2:
                    msg = exc2.message or ""
                    already = any(
                        k in msg for k in ("已签到", "重复签到", "签到过", "already")
                    )
                    game_name = role.game_name if role else game_code
                    role_name = role.role_name if role else "-"
                    channel = role.game_name if role else game_code
                    result = CheckinResult(
                        game_code=game_code,
                        game_name=game_name,
                        role_uid=role_uid,
                        role_name=role_name,
                        channel_name=channel,
                        status="already" if already else "error",
                        message=(
                            "今日已签到"
                            if already
                            else friendly_error_message(msg)
                        ),
                    )
                else:
                    results.append(result)
                    continue
            else:
                msg = exc.message or ""
                already = any(k in msg for k in ("已签到", "重复签到", "签到过", "already"))
                game_name = role.game_name if role else game_code
                role_name = role.role_name if role else "-"
                channel = role.game_name if role else game_code
                result = CheckinResult(
                    game_code=game_code,
                    game_name=game_name,
                    role_uid=role_uid,
                    role_name=role_name,
                    channel_name=channel,
                    status="already" if already else "error",
                    message=(
                        "今日已签到" if already else friendly_error_message(msg)
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("taygedo checkin unexpected error")
            game_name = role.game_name if role else game_code
            role_name = role.role_name if role else "-"
            channel = role.game_name if role else game_code
            result = CheckinResult(
                game_code=game_code,
                game_name=game_name,
                role_uid=role_uid,
                role_name=role_name,
                channel_name=channel,
                status="error",
                message=friendly_error_message(str(exc)),
            )
        results.append(result)

    _save_creds(bind, working)
    ok, summary = _summarize(results)
    now = now_naive()
    bind.last_checkin_at = now
    bind.last_checkin_date = checkin_date
    bind.last_checkin_ok = ok
    bind.last_checkin_summary = summary
    bind.updated_at = now
    merged = upsert_and_reload_day_results(
        db,
        TaygedoCheckinLog,
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
        raise TaygedoApiError("尚未绑定塔吉多")
    return run_checkin_for_bind(db, bind, force=force)


def run_taygedo_checkin_job(db: Session) -> dict[str, Any]:
    binds = (
        db.query(TaygedoBind)
        .options(joinedload(TaygedoBind.member))
        .filter(TaygedoBind.auto_checkin.is_(True))
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
            logger.exception("taygedo auto checkin failed member_id=%s", bind.member_id)
            stats["failed"] += 1
            db.rollback()
    return stats


def checkin_job_wrapper() -> None:
    from app.core.database import SessionLocal

    if not _job_lock.acquire(blocking=False):
        logger.info("taygedo checkin job already running, skip")
        return
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        stats = run_taygedo_checkin_job(db)
        job.status = "ok"
        job.message = (
            f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
            f"跳过 {stats['skipped']}（共 {stats['total']}）"
        )
        job.stats = stats
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("taygedo checkin job crashed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
        _job_lock.release()
