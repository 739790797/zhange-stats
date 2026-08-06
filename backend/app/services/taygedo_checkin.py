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
from app.models.taygedo import TaygedoAttendanceRaw, TaygedoBind, TaygedoCheckinLog
from app.services.checkin_common import (
    CheckinResult,
    apply_bind_last_checkin,
    day_results_payload,
    is_success_status,
    load_day_checkin_results,
    results_to_api,
    summarize_results,
    today_done_from_logs,
    upsert_and_reload_day_results,
)
from app.services.taygedo_calendar import parse_taygedo_attendance_calendar
from app.services.taygedo_client import (
    GAME_HT,
    GAME_NTE,
    TaygedoApiError,
    TaygedoCredentials,
    TaygedoRole,
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
        bind = TaygedoBind(member_id=member.id, credentials_enc="", auto_checkin=False)
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
        bind = TaygedoBind(member_id=member.id, credentials_enc="", auto_checkin=False)
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
        bind = TaygedoBind(member_id=member.id, credentials_enc="", auto_checkin=False)
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
    return update_bind_prefs(db, member, auto_checkin=bool(enabled))


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> TaygedoBind:
    from app.services.checkin_schedule import clamp_checkin_hour, clamp_checkin_minute

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
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


_CALENDAR_GAMES = frozenset({GAME_NTE, GAME_HT})


def _taygedo_today_log_hint(
    db: Session, *, member_id: int, game_code: str, role_uid: str
) -> bool:
    from app.services.checkin_common import SUCCESS_STATUSES

    row = (
        db.query(TaygedoCheckinLog)
        .filter(
            TaygedoCheckinLog.member_id == member_id,
            TaygedoCheckinLog.game_code == game_code,
            TaygedoCheckinLog.role_uid == role_uid,
            TaygedoCheckinLog.checkin_date == today(),
            TaygedoCheckinLog.status.in_(tuple(SUCCESS_STATUSES)),
        )
        .one_or_none()
    )
    return row is not None


def invalidate_taygedo_attendance_raws(
    db: Session,
    member_id: int,
    *,
    game_code: str | None = None,
    role_uids: list[str] | None = None,
) -> None:
    """签到成功后丢弃日历 raw，下次打开页回源。"""
    q = db.query(TaygedoAttendanceRaw).filter(
        TaygedoAttendanceRaw.member_id == member_id
    )
    if game_code:
        q = q.filter(TaygedoAttendanceRaw.game_code == game_code)
    if role_uids:
        q = q.filter(TaygedoAttendanceRaw.role_uid.in_(role_uids))
    q.delete(synchronize_session=False)


def get_taygedo_attendance_calendar_for_member(
    db: Session,
    member: Member,
    *,
    game_code: str,
    role_uid: str | None = None,
    force: bool = False,
) -> tuple[dict[str, Any], TaygedoRole, list[TaygedoRole], datetime | None, bool]:
    """读库二次加工异环/幻塔签到日历；无记录、跨月或 force 时回源落库。"""
    from datetime import datetime

    from app.core.timeutil import BEIJING, now as beijing_now
    from app.services.raw_payload_monitor import note_raw_payload
    from app.services.taygedo_attendance import fetch_game_attendance_bundle
    from app.services.taygedo_client import ensure_access_token, list_game_roles

    game_code = str(game_code or "").strip()
    if game_code not in _CALENDAR_GAMES:
        raise TaygedoApiError("仅异环 / 幻塔支持签到日历")

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")

    creds = _load_creds(bind)
    try:
        working = ensure_access_token(creds)
        game_name = "异环" if game_code == GAME_NTE else "幻塔"
        roles = list_game_roles(working, game_code, game_name)
    except TaygedoApiError as exc:
        raise TaygedoApiError(friendly_error_message(exc.message)) from exc
    _save_creds(bind, working)
    db.commit()

    if not roles:
        raise TaygedoApiError(f"未找到{game_name}绑定角色")

    target_uid = str(role_uid or "").strip()
    role = (
        next((r for r in roles if r.role_id == target_uid), None)
        if target_uid
        else roles[0]
    )
    if role is None:
        raise TaygedoApiError("角色不在当前塔吉多绑定列表中")

    row = (
        db.query(TaygedoAttendanceRaw)
        .filter(
            TaygedoAttendanceRaw.member_id == member.id,
            TaygedoAttendanceRaw.game_code == game_code,
            TaygedoAttendanceRaw.role_uid == role.role_id,
        )
        .one_or_none()
    )

    def _same_beijing_month(synced_at: datetime | None) -> bool:
        if synced_at is None:
            return False
        now = beijing_now()
        if synced_at.tzinfo is None:
            synced = synced_at.replace(tzinfo=BEIJING)
        else:
            synced = synced_at.astimezone(BEIJING)
        return (synced.year, synced.month) == (now.year, now.month)

    stale = False
    need_fetch = force or row is None or not _same_beijing_month(row.synced_at)
    if need_fetch:
        try:
            bundle = fetch_game_attendance_bundle(
                working, game_code, role_id=role.role_id
            )
            raw_json = json.dumps(bundle, ensure_ascii=False)
            note_raw_payload(
                "taygedo_attendance_raw",
                raw_json,
                member_id=member.id,
                uid=role.role_id,
            )
            synced = now_naive()
            if row is None:
                row = TaygedoAttendanceRaw(
                    member_id=member.id,
                    game_code=game_code,
                    role_uid=role.role_id,
                    role_name=role.role_name,
                    game_name=role.game_name,
                    raw_json=raw_json,
                    synced_at=synced,
                )
                db.add(row)
            else:
                row.role_name = role.role_name
                row.game_name = role.game_name
                row.raw_json = raw_json
                row.synced_at = synced
            db.commit()
            db.refresh(row)
        except TaygedoApiError as exc:
            if row is None:
                raise TaygedoApiError(friendly_error_message(exc.message)) from exc
            stale = True
            logger.warning(
                "taygedo attendance refresh failed member_id=%s game=%s role=%s: %s",
                member.id,
                game_code,
                role.role_id,
                exc.message,
            )

    try:
        resp = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise TaygedoApiError("签到日历数据损坏，请刷新重试") from exc
    if not isinstance(resp, dict):
        raise TaygedoApiError("签到日历数据格式异常，请刷新重试")

    log_today = _taygedo_today_log_hint(
        db, member_id=member.id, game_code=game_code, role_uid=role.role_id
    )
    parsed = parse_taygedo_attendance_calendar(
        resp,
        fallback_has_today=True if log_today else None,
    )
    return parsed, role, roles, row.synced_at, stale


def run_checkin_for_bind(
    db: Session,
    bind: TaygedoBind,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """手动 / 自动签到；结果写入今日签到日志。"""
    from app.services.checkin_role_prefs import matches_role_filter
    from app.services.taygedo_client import list_checkin_targets

    checkin_date = today()
    if not force:
        done = today_done_from_logs(
            db,
            TaygedoCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
            role_keys=role_keys,
        )
        if done is not None:
            full = load_day_checkin_results(
                db,
                TaygedoCheckinLog,
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
    working, targets = list_checkin_targets(creds)
    _save_creds(bind, working)

    if role_keys is not None:
        filtered = []
        for game_code, role in targets:
            role_uid = role.role_id if role else "-"
            if matches_role_filter(game_code, role_uid, role_keys):
                filtered.append((game_code, role))
        targets = filtered

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
    apply_bind_last_checkin(
        bind, now=now, checkin_date=checkin_date, ok=ok, summary=summary
    )
    merged = upsert_and_reload_day_results(
        db,
        TaygedoCheckinLog,
        member_id=bind.member_id,
        bind_id=bind.id,
        checkin_date=checkin_date,
        results=results,
        now=now,
    )
    cal_uids = [
        r.role_uid
        for r in results
        if r.game_code in _CALENDAR_GAMES and is_success_status(r.status)
    ]
    if cal_uids:
        invalidate_taygedo_attendance_raws(
            db, bind.member_id, role_uids=cal_uids
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


def run_taygedo_checkin_job(
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    from app.services.checkin_role_prefs import (
        PLATFORM_TAYGEDO,
        collect_checkin_job_targets,
    )

    targets = collect_checkin_job_targets(
        db,
        platform=PLATFORM_TAYGEDO,
        bind_model=TaygedoBind,
        due_only=due_only,
        member_id=member_id,
    )
    binds_by_member = {
        b.member_id: b
        for b in db.query(TaygedoBind)
        .options(joinedload(TaygedoBind.member))
        .filter(TaygedoBind.member_id.in_(list(targets.keys()) or [-1]))
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
            out = run_checkin_for_bind(db, bind, force=False, role_keys=role_keys)
            if out.get("skipped"):
                stats["skipped"] += 1
            elif out.get("ok"):
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("taygedo auto checkin failed member_id=%s", mid)
            stats["failed"] += 1
            db.rollback()
    return stats


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
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
        stats = run_taygedo_checkin_job(db, due_only=due_only, member_id=member_id)
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
