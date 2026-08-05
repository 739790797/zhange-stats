"""森空岛绑定与每日签到编排。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.endfield import EndfieldBoxRaw
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.skland import SklandBind, SklandCheckinLog
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
from app.services.skland_client import (
    SklandApiError,
    SklandRole,
    checkin_role,
    fetch_arknights_box,
    fetch_endfield_card_detail,
    friendly_error_message,
    list_roles,
    login_with_token,
    normalize_hg_token,
    parse_endfield_box,
    query_role_today,
    query_today_all,
    sort_skland_results,
    GAME_ARKNIGHTS,
    GAME_ENDFIELD,
)

logger = logging.getLogger(__name__)

JOB_KEY = "skland_checkin"
_job_lock = threading.Lock()


def get_bind_for_member(db: Session, member_id: int) -> SklandBind | None:
    return db.query(SklandBind).filter(SklandBind.member_id == member_id).one_or_none()


def bind_skland(db: Session, member: Member, raw_token: str) -> SklandBind:
    token = normalize_hg_token(raw_token)
    session = login_with_token(token)
    list_roles(session)

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = SklandBind(
            member_id=member.id,
            token_enc=encrypt_secret(token),
            auto_checkin=True,
        )
        db.add(bind)
    else:
        bind.token_enc = encrypt_secret(token)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def _maybe_checkin_after_bind(db: Session, bind: SklandBind) -> None:
    """绑定成功后：若开启自动签到且今日尚未签到，则立即补签。"""
    if not bind.auto_checkin:
        return
    try:
        run_checkin_for_bind(db, bind, force=False)
    except Exception:  # noqa: BLE001
        logger.exception(
            "skland checkin after bind failed member_id=%s", bind.member_id
        )
        db.rollback()
        db.refresh(bind)


def bind_skland_with_password(
    db: Session, member: Member, phone: str, password: str
) -> SklandBind:
    from app.services.skland_client import token_by_phone_password

    return bind_skland(db, member, token_by_phone_password(phone, password))


def bind_skland_with_sms(db: Session, member: Member, phone: str, code: str) -> SklandBind:
    from app.services.skland_client import token_by_phone_code

    return bind_skland(db, member, token_by_phone_code(phone, code))


def send_skland_sms(phone: str) -> None:
    from app.services.skland_client import send_phone_code

    send_phone_code(phone)


def unbind_skland(db: Session, member: Member) -> None:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return
    db.delete(bind)
    db.commit()


def set_auto_checkin(db: Session, member: Member, enabled: bool) -> SklandBind:
    return update_bind_prefs(db, member, auto_checkin=bool(enabled))


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> SklandBind:
    from app.services.checkin_schedule import clamp_checkin_hour, clamp_checkin_minute

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
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


def preview_roles(db: Session, member: Member) -> list[SklandRole]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    token = decrypt_secret(bind.token_enc)
    if not token:
        raise SklandApiError("凭证已损坏，请重新绑定")
    session = login_with_token(token)
    return list_roles(session)


def get_arknights_box_for_member(db: Session, member: Member, uid: str | None = None):
    """拉取指定（或默认）明日方舟账号的干员盒子。"""
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    session = _session_for_bind(bind)
    roles = [r for r in list_roles(session) if r.game_code == GAME_ARKNIGHTS]
    if not roles:
        raise SklandApiError("未找到明日方舟绑定角色")
    target_uid = str(uid or "").strip()
    role = next((r for r in roles if r.uid == target_uid), None) if target_uid else roles[0]
    if role is None:
        raise SklandApiError("UID 不在当前森空岛绑定列表中")
    box = fetch_arknights_box(session, role.uid)
    return box, role, roles


def get_endfield_box_for_member(
    db: Session,
    member: Member,
    uid: str | None = None,
    *,
    force: bool = False,
):
    """读库二次加工终末地养成盒；无记录或 force 时回源落库。"""
    import json

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    session = _session_for_bind(bind)
    roles = [r for r in list_roles(session) if r.game_code == GAME_ENDFIELD]
    if not roles:
        raise SklandApiError("未找到终末地绑定角色")
    target_uid = str(uid or "").strip()
    role = None
    if target_uid:
        role = next(
            (
                r
                for r in roles
                if r.uid == target_uid or r.role_id == target_uid
            ),
            None,
        )
    else:
        role = roles[0]
    if role is None:
        raise SklandApiError("UID 不在当前终末地绑定列表中")
    if not role.role_id:
        raise SklandApiError("终末地角色缺少 roleId，请重新绑定森空岛")

    row = (
        db.query(EndfieldBoxRaw)
        .filter(
            EndfieldBoxRaw.member_id == member.id,
            EndfieldBoxRaw.role_id == str(role.role_id),
        )
        .one_or_none()
    )
    stale = False
    if force or row is None:
        try:
            raw = fetch_endfield_card_detail(session, role)
            raw_json = json.dumps(raw, ensure_ascii=False)
            from app.services.raw_payload_monitor import note_raw_payload

            note_raw_payload(
                "endfield_box_raw",
                raw_json,
                member_id=member.id,
                role_id=role.role_id,
            )
            now = now_naive()
            if row is None:
                row = EndfieldBoxRaw(
                    member_id=member.id,
                    role_id=str(role.role_id),
                    server_id=str(role.server_id or ""),
                    uid=str(role.uid or role.role_id),
                    raw_json=raw_json,
                    synced_at=now,
                )
                db.add(row)
            else:
                row.server_id = str(role.server_id or "")
                row.uid = str(role.uid or role.role_id)
                row.raw_json = raw_json
                row.synced_at = now
            db.commit()
            db.refresh(row)
        except SklandApiError:
            if row is None:
                raise
            stale = True
            logger.exception(
                "endfield card refresh failed member_id=%s role_id=%s",
                member.id,
                role.role_id,
            )

    try:
        raw_obj = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise SklandApiError("终末地养成数据损坏，请刷新重试") from exc
    if not isinstance(raw_obj, dict):
        raise SklandApiError("终末地养成数据格式异常，请刷新重试")

    box = parse_endfield_box(raw_obj, role=role)
    return box, role, roles, row.synced_at, stale


def _summarize(results: list[CheckinResult]) -> tuple[bool, str]:
    return summarize_results(
        results,
        empty_message="未找到可签到的游戏角色（请确认已在森空岛绑定明日方舟 / 终末地）",
    )


def _session_for_bind(bind: SklandBind):
    token = decrypt_secret(bind.token_enc)
    if not token:
        raise SklandApiError("凭证已损坏，请重新绑定")
    return login_with_token(token)


def query_today_for_bind(
    db: Session, bind: SklandBind, *, force: bool = False
) -> dict[str, Any]:
    """今日签到状态：有今日日志则读库；否则查官方并落库。"""
    checkin_date = today()
    if not force:
        cached = load_day_checkin_results(
            db,
            SklandCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
        )
        if cached is not None:
            cached = sort_skland_results(cached)
            return day_results_payload(cached)

    session = _session_for_bind(bind)
    try:
        results = query_today_all(session)
    except SklandApiError as exc:
        raise SklandApiError(friendly_error_message(exc.message)) from exc
    results = sort_skland_results(results)
    now = now_naive()
    merged = sort_skland_results(
        upsert_and_reload_day_results(
            db,
            SklandCheckinLog,
            member_id=bind.member_id,
            bind_id=bind.id,
            checkin_date=checkin_date,
            results=results,
            now=now,
        )
    )
    db.commit()
    return day_results_payload(merged)


def query_today_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    return query_today_for_bind(db, bind, force=force)


def run_checkin_for_bind(
    db: Session,
    bind: SklandBind,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """手动 / 自动签到；结果写入今日签到日志。"""
    checkin_date = today()
    if not force:
        done = today_done_from_logs(
            db,
            SklandCheckinLog,
            member_id=bind.member_id,
            checkin_date=checkin_date,
        )
        if done is not None:
            payload = day_results_payload(done)
            return {
                "skipped": True,
                "ok": True,
                "reason": "today_done",
                "summary": payload.get("summary") or "今日已签到",
                "results": payload.get("results") or [],
            }

    session = _session_for_bind(bind)
    roles = list_roles(session)
    if not roles:
        return {
            "skipped": False,
            "ok": False,
            "summary": "未找到可签到的游戏角色（请确认已在森空岛绑定明日方舟 / 终末地）",
            "results": [],
        }

    results: list[CheckinResult] = []
    for role in roles:
        # 先查今日：已签则只补奖励，不 POST
        if not force:
            probed = query_role_today(session, role)
            if is_success_status(probed.status):
                results.append(probed)
                continue
        try:
            result = checkin_role(session, role)
        except SklandApiError as exc:
            msg = exc.message or ""
            already = "请勿重复签到" in msg or "重复签到" in msg
            if already:
                result = query_role_today(session, role)
                if result.status == "pending":
                    result = CheckinResult(
                        game_code=role.game_code,
                        game_name=role.game_name,
                        role_uid=role.uid,
                        role_name=role.role_name,
                        channel_name=role.channel_name,
                        status="already",
                        message="今日已签到",
                    )
            else:
                result = CheckinResult(
                    game_code=role.game_code,
                    game_name=role.game_name,
                    role_uid=role.uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    status="error",
                    message=friendly_error_message(msg),
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("skland checkin unexpected error")
            result = CheckinResult(
                game_code=role.game_code,
                game_name=role.game_name,
                role_uid=role.uid,
                role_name=role.role_name,
                channel_name=role.channel_name,
                status="error",
                message=friendly_error_message(str(exc)),
            )
        results.append(result)

    results = sort_skland_results(results)
    ok, summary = _summarize(results)
    now = now_naive()
    apply_bind_last_checkin(
        bind, now=now, checkin_date=checkin_date, ok=ok, summary=summary
    )
    merged = sort_skland_results(
        upsert_and_reload_day_results(
            db,
            SklandCheckinLog,
            member_id=bind.member_id,
            bind_id=bind.id,
            checkin_date=checkin_date,
            results=results,
            now=now,
        )
    )
    db.commit()

    return {
        "skipped": False,
        "summary": summary,
        "ok": ok,
        "results": results_to_api(merged),
    }


def run_checkin_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    return run_checkin_for_bind(db, bind, force=force)


def run_skland_checkin_job(
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    from app.core.timeutil import now as now_beijing

    q = (
        db.query(SklandBind)
        .options(joinedload(SklandBind.member))
        .filter(SklandBind.auto_checkin.is_(True))
    )
    if member_id is not None:
        q = q.filter(SklandBind.member_id == int(member_id))
    elif due_only:
        t = now_beijing()
        q = q.filter(
            SklandBind.checkin_hour == t.hour,
            SklandBind.checkin_minute == t.minute,
        )
    binds = q.all()
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
            logger.exception("skland auto checkin failed member_id=%s", bind.member_id)
            stats["failed"] += 1
            db.rollback()
    return stats


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    from app.core.database import SessionLocal

    if not _job_lock.acquire(blocking=False):
        logger.info("skland checkin job already running, skip")
        return
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        stats = run_skland_checkin_job(db, due_only=due_only, member_id=member_id)
        job.status = "ok"
        job.message = (
            f"完成：成功 {stats['ok']} / 失败 {stats['failed']} / "
            f"跳过 {stats['skipped']}（共 {stats['total']}）"
        )
        job.stats = stats
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("skland checkin job crashed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
        _job_lock.release()
