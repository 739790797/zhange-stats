"""森空岛绑定与每日签到编排。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.endfield import EndfieldAttendanceRaw, EndfieldBoxRaw
from app.models.member import Member
from app.models.skland import SklandAttendanceRaw, SklandBind, SklandCheckinLog
from app.services.checkin.adapter import CheckinAdapterBase, CheckinRunOutcome
from app.services.checkin.common import CheckinResult, is_success_status
from app.services.checkin.orchestrator import (
    checkin_job_wrapper as _orch_job_wrapper,
)
from app.services.checkin.orchestrator import (
    query_today_for_bind as _orch_query_today,
)
from app.services.checkin.orchestrator import (
    run_checkin_for_bind as _orch_run_checkin,
)
from app.services.checkin.role_prefs import (
    PLATFORM_SKLAND,
    RoleKey,
    matches_role_filter,
)
from app.services.skland.client import (
    GAME_ARKNIGHTS,
    GAME_ENDFIELD,
    SklandApiError,
    SklandRole,
    SklandSession,
    localize_arknights_channel_name,
    localize_endfield_server_name,
    login_with_token,
    normalize_hg_token,
)
from app.services.skland.endfield_calendar import parse_endfield_attendance_calendar
from app.services.skland.calendar import parse_arknights_attendance_calendar
from app.services.skland.attendance import (
    _is_arknights_bilibili,
    checkin_role,
    fetch_arknights_attendance,
    fetch_endfield_attendance,
    friendly_error_message,
    list_roles,
    query_role_today,
    query_today_all as skland_query_today_all,
    sort_skland_results,
)
from app.services.skland.boxes import (
    fetch_arknights_box,
    fetch_endfield_card_detail,
    parse_endfield_box,
)

logger = logging.getLogger(__name__)

JOB_KEY = "skland_checkin"


def get_bind_for_member(db: Session, member_id: int) -> SklandBind | None:
    return db.query(SklandBind).filter(SklandBind.member_id == member_id).one_or_none()


def _looks_like_skland_auth_error(message: str | None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    low = text.lower()
    return any(
        k in text
        for k in ("未登录", "登录", "凭证", "cred", "token", "授权", "过期", "失效")
    ) or "unauthorized" in low


def bind_skland(db: Session, member: Member, raw_token: str) -> SklandBind:
    from app.services.skland.session_cache import (
        invalidate_skland_session,
        put_cached_skland_session,
    )

    token = normalize_hg_token(raw_token)
    # 换票前先清缓存，避免旧 cred 与并发 status 交错
    invalidate_skland_session(member.id)
    session = login_with_token(token)
    list_roles(session)

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = SklandBind(
            member_id=member.id,
            token_enc=encrypt_secret(token),
            auto_checkin=False,
        )
        db.add(bind)
    else:
        bind.token_enc = encrypt_secret(token)
    bind.updated_at = now_naive()
    db.commit()
    db.refresh(bind)
    put_cached_skland_session(member.id, token, session)
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
    from app.services.skland.client import token_by_phone_password

    return bind_skland(db, member, token_by_phone_password(phone, password))


def bind_skland_with_sms(db: Session, member: Member, phone: str, code: str) -> SklandBind:
    from app.services.skland.client import token_by_phone_code

    return bind_skland(db, member, token_by_phone_code(phone, code))


def send_skland_sms(phone: str) -> None:
    from app.services.skland.client import send_phone_code

    send_phone_code(phone)


def unbind_skland(db: Session, member: Member) -> None:
    from app.services.skland.session_cache import invalidate_skland_session

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return
    db.delete(bind)
    db.commit()
    invalidate_skland_session(member.id)


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> SklandBind:
    from app.services.checkin.schedule import clamp_checkin_hour, clamp_checkin_minute

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
    # 复用会话缓存，避免绑定后立刻再 grant 一次把刚写入的 cred 顶掉
    return list_roles(_session_for_bind(bind))


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


def _arknights_today_log_hint(
    db: Session, *, member_id: int, role_uid: str
) -> tuple[bool, list[dict[str, Any]] | None]:
    """今日本地签到日志：是否已签 + 结构化奖励（供奖励唯一匹配推断进度）。"""
    from app.services.checkin.common import SUCCESS_STATUSES, loads_awards_json

    row = (
        db.query(SklandCheckinLog)
        .filter(
            SklandCheckinLog.member_id == member_id,
            SklandCheckinLog.role_uid == role_uid,
            SklandCheckinLog.game_code == GAME_ARKNIGHTS,
            SklandCheckinLog.checkin_date == today(),
            SklandCheckinLog.status.in_(tuple(SUCCESS_STATUSES)),
        )
        .one_or_none()
    )
    if row is None:
        return False, None
    awards = None
    if getattr(row, "awards_json", None):
        awards = loads_awards_json(row.awards_json)
    return True, awards


def get_arknights_attendance_calendar_for_member(
    db: Session,
    member: Member,
    uid: str | None = None,
    *,
    force: bool = False,
) -> tuple[dict[str, Any], SklandRole, list[SklandRole], datetime | None, bool]:
    """读库二次加工方舟签到日历；无记录、跨月或 force 时回源落库。"""
    import json

    from app.core.timeutil import BEIJING, now as beijing_now
    from app.services.raw_payload_monitor import note_raw_payload

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    session: SklandSession | None = None

    def _ensure_session() -> SklandSession:
        nonlocal session
        if session is None:
            session = _session_for_bind(bind)
        return session

    roles: list[SklandRole] | None = None
    if not force:
        from app.services.box_role_cache import skland_arknights_roles_from_raws

        roles = skland_arknights_roles_from_raws(db, member.id)
    if roles is None:
        roles = [
            r for r in list_roles(_ensure_session()) if r.game_code == GAME_ARKNIGHTS
        ]
    if not roles:
        raise SklandApiError("未找到明日方舟绑定角色")
    target_uid = str(uid or "").strip()
    role = next((r for r in roles if r.uid == target_uid), None) if target_uid else roles[0]
    if role is None:
        raise SklandApiError("UID 不在当前森空岛绑定列表中")

    row = (
        db.query(SklandAttendanceRaw)
        .filter(
            SklandAttendanceRaw.member_id == member.id,
            SklandAttendanceRaw.uid == role.uid,
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
            resp = fetch_arknights_attendance(_ensure_session(), role)
            raw_json = json.dumps(resp, ensure_ascii=False)
            note_raw_payload(
                "skland_attendance_raw",
                raw_json,
                member_id=member.id,
                uid=role.uid,
            )
            synced = now_naive()
            if row is None:
                row = SklandAttendanceRaw(
                    member_id=member.id,
                    uid=role.uid,
                    channel_name=role.channel_name,
                    role_name=role.role_name,
                    raw_json=raw_json,
                    synced_at=synced,
                )
                db.add(row)
            else:
                row.channel_name = role.channel_name
                row.role_name = role.role_name
                row.raw_json = raw_json
                row.synced_at = synced
            db.commit()
            db.refresh(row)
        except SklandApiError as exc:
            if row is None:
                raise SklandApiError(friendly_error_message(exc.message)) from exc
            stale = True
            logger.warning(
                "arknights attendance refresh failed member_id=%s uid=%s: %s",
                member.id,
                role.uid,
                exc.message,
            )

    try:
        resp = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise SklandApiError("签到日历数据损坏，请刷新重试") from exc
    if not isinstance(resp, dict):
        raise SklandApiError("签到日历数据格式异常，请刷新重试")

    log_today, log_awards = _arknights_today_log_hint(
        db, member_id=member.id, role_uid=role.uid
    )
    parsed = parse_arknights_attendance_calendar(
        resp,
        fallback_has_today=True if log_today else None,
        fallback_today_awards=log_awards,
    )
    return parsed, role, roles, row.synced_at, stale


def invalidate_arknights_attendance_raws(
    db: Session, member_id: int, *, uids: list[str] | None = None
) -> None:
    """签到成功后丢弃日历 raw，下次打开页回源。"""
    q = db.query(SklandAttendanceRaw).filter(
        SklandAttendanceRaw.member_id == member_id
    )
    if uids:
        q = q.filter(SklandAttendanceRaw.uid.in_(uids))
    q.delete(synchronize_session=False)


def _endfield_today_log_hint(
    db: Session, *, member_id: int, role_uid: str
) -> bool:
    """今日本地签到日志是否已成功（供日历 hasToday 回退）。"""
    from app.services.checkin.common import SUCCESS_STATUSES

    row = (
        db.query(SklandCheckinLog)
        .filter(
            SklandCheckinLog.member_id == member_id,
            SklandCheckinLog.role_uid == role_uid,
            SklandCheckinLog.game_code == GAME_ENDFIELD,
            SklandCheckinLog.checkin_date == today(),
            SklandCheckinLog.status.in_(tuple(SUCCESS_STATUSES)),
        )
        .one_or_none()
    )
    return row is not None


def get_endfield_attendance_calendar_for_member(
    db: Session,
    member: Member,
    uid: str | None = None,
    *,
    force: bool = False,
) -> tuple[dict[str, Any], SklandRole, list[SklandRole], datetime | None, bool]:
    """读库二次加工终末地签到日历；无记录、跨月或 force 时回源落库。"""
    import json

    from app.core.timeutil import BEIJING, now as beijing_now
    from app.services.raw_payload_monitor import note_raw_payload

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    session: SklandSession | None = None

    def _ensure_session() -> SklandSession:
        nonlocal session
        if session is None:
            session = _session_for_bind(bind)
        return session

    roles: list[SklandRole] | None = None
    if not force:
        from app.services.box_role_cache import skland_endfield_roles_from_raws

        roles = skland_endfield_roles_from_raws(db, member.id)
    if roles is None:
        roles = [
            r for r in list_roles(_ensure_session()) if r.game_code == GAME_ENDFIELD
        ]
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
        db.query(EndfieldAttendanceRaw)
        .filter(
            EndfieldAttendanceRaw.member_id == member.id,
            EndfieldAttendanceRaw.role_id == str(role.role_id),
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
            resp = fetch_endfield_attendance(_ensure_session(), role)
            raw_json = json.dumps(resp, ensure_ascii=False)
            note_raw_payload(
                "endfield_attendance_raw",
                raw_json,
                member_id=member.id,
                uid=role.uid,
            )
            synced = now_naive()
            if row is None:
                row = EndfieldAttendanceRaw(
                    member_id=member.id,
                    role_id=str(role.role_id),
                    server_id=str(role.server_id or ""),
                    uid=role.uid,
                    role_name=role.role_name,
                    channel_name=role.channel_name,
                    raw_json=raw_json,
                    synced_at=synced,
                )
                db.add(row)
            else:
                row.server_id = str(role.server_id or "")
                row.uid = role.uid
                row.role_name = role.role_name
                row.channel_name = role.channel_name
                row.raw_json = raw_json
                row.synced_at = synced
            db.commit()
            db.refresh(row)
        except SklandApiError as exc:
            if row is None:
                raise SklandApiError(friendly_error_message(exc.message)) from exc
            stale = True
            logger.warning(
                "endfield attendance refresh failed member_id=%s role_id=%s: %s",
                member.id,
                role.role_id,
                exc.message,
            )

    try:
        resp = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise SklandApiError("签到日历数据损坏，请刷新重试") from exc
    if not isinstance(resp, dict):
        raise SklandApiError("签到日历数据格式异常，请刷新重试")

    log_today = _endfield_today_log_hint(
        db, member_id=member.id, role_uid=role.uid
    )
    parsed = parse_endfield_attendance_calendar(
        resp,
        fallback_has_today=True if log_today else None,
    )
    return parsed, role, roles, row.synced_at, stale


def invalidate_endfield_attendance_raws(
    db: Session, member_id: int, *, uids: list[str] | None = None
) -> None:
    """签到成功后丢弃终末地日历 raw，下次打开页回源。"""
    q = db.query(EndfieldAttendanceRaw).filter(
        EndfieldAttendanceRaw.member_id == member_id
    )
    if uids:
        q = q.filter(EndfieldAttendanceRaw.uid.in_(uids))
    q.delete(synchronize_session=False)


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
    session: SklandSession | None = None

    def _ensure_session() -> SklandSession:
        nonlocal session
        if session is None:
            session = _session_for_bind(bind)
        return session

    roles: list[SklandRole] | None = None
    if not force:
        from app.services.box_role_cache import skland_endfield_roles_from_raws

        roles = skland_endfield_roles_from_raws(db, member.id)
    if roles is None:
        roles = [
            r for r in list_roles(_ensure_session()) if r.game_code == GAME_ENDFIELD
        ]
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
            raw = fetch_endfield_card_detail(_ensure_session(), role)
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


def get_arknights_rogue_for_member(
    db: Session,
    member: Member,
    uid: str | None = None,
    *,
    topic_id: str | None = None,
    force: bool = False,
):
    """读库二次加工方舟肉鸽；无记录或 force 时回源落库。"""
    import json

    from app.models.arknights_rogue import ArknightsRogueRaw
    from app.services.skland.rogue import (
        DEFAULT_TOPIC_ID,
        fetch_arknights_rogue,
        normalize_topic_id,
        parse_arknights_rogue,
    )
    from app.services.skland.session_cache import put_cached_skland_session

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    session: SklandSession | None = None

    def _ensure_session() -> SklandSession:
        nonlocal session
        if session is None:
            session = _session_for_bind(bind)
        return session

    roles: list[SklandRole] | None = None
    if not force:
        from app.services.box_role_cache import skland_arknights_roles_from_raws

        roles = skland_arknights_roles_from_raws(db, member.id)
    if roles is None:
        roles = [
            r for r in list_roles(_ensure_session()) if r.game_code == GAME_ARKNIGHTS
        ]
    if not roles:
        raise SklandApiError("未找到明日方舟绑定角色")
    target_uid = str(uid or "").strip()
    role = None
    if target_uid:
        role = next((r for r in roles if r.uid == target_uid), None)
    else:
        role = roles[0]
    if role is None:
        raise SklandApiError("UID 不在当前明日方舟绑定列表中")

    topic = normalize_topic_id(topic_id) if topic_id else DEFAULT_TOPIC_ID
    row = (
        db.query(ArknightsRogueRaw)
        .filter(
            ArknightsRogueRaw.member_id == member.id,
            ArknightsRogueRaw.uid == str(role.uid),
            ArknightsRogueRaw.topic_id == topic,
        )
        .one_or_none()
    )
    stale = False
    if force or row is None:
        try:
            sess = _ensure_session()
            raw = fetch_arknights_rogue(sess, uid=str(role.uid), topic_id=topic)
            # user_id 可能在本次拉取中补齐，写回会话缓存
            token = decrypt_secret(bind.token_enc)
            if token and sess.user_id:
                put_cached_skland_session(member.id, token, sess)
            raw_json = json.dumps(raw, ensure_ascii=False)
            from app.services.raw_payload_monitor import note_raw_payload

            note_raw_payload(
                "arknights_rogue_raw",
                raw_json,
                member_id=member.id,
                uid=role.uid,
                topic_id=topic,
            )
            now = now_naive()
            if row is None:
                row = ArknightsRogueRaw(
                    member_id=member.id,
                    uid=str(role.uid),
                    topic_id=topic,
                    raw_json=raw_json,
                    synced_at=now,
                )
                db.add(row)
            else:
                row.raw_json = raw_json
                row.synced_at = now
            db.commit()
            db.refresh(row)
        except SklandApiError:
            if row is None:
                raise
            stale = True
            logger.exception(
                "arknights rogue refresh failed member_id=%s uid=%s topic=%s",
                member.id,
                role.uid,
                topic,
            )

    try:
        raw_obj = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise SklandApiError("肉鸽数据损坏，请刷新重试") from exc
    if not isinstance(raw_obj, dict):
        raise SklandApiError("肉鸽数据格式异常，请刷新重试")

    box = parse_arknights_rogue(raw_obj, topic_id=topic)
    return box, role, roles, row.synced_at, stale


def _session_for_bind(bind: SklandBind, *, bypass_cache: bool = False):
    from app.services.skland.session_cache import (
        get_cached_skland_session,
        invalidate_skland_session,
        put_cached_skland_session,
    )

    token = decrypt_secret(bind.token_enc)
    if not token:
        raise SklandApiError("凭证已损坏，请重新绑定")
    if not bypass_cache:
        cached = get_cached_skland_session(bind.member_id, token)
        if cached is not None:
            return cached
    else:
        invalidate_skland_session(bind.member_id)
    session = login_with_token(token)
    put_cached_skland_session(bind.member_id, token, session)
    return session


_EMPTY_ROLES_MSG = (
    "未找到可签到的游戏角色（请确认已在森空岛绑定明日方舟 / 终末地）"
)


class SklandCheckinAdapter(CheckinAdapterBase):
    platform = PLATFORM_SKLAND
    job_key = JOB_KEY
    bind_model = SklandBind
    log_model = SklandCheckinLog
    api_error_cls = SklandApiError
    empty_message = _EMPTY_ROLES_MSG

    def get_bind(self, db: Session, member_id: int) -> SklandBind | None:
        return get_bind_for_member(db, member_id)

    def load_session(self, db: Session, bind: SklandBind):
        return _session_for_bind(bind)

    def query_today_all(self, session) -> tuple[Any, list[CheckinResult]]:
        return skland_query_today_all(session)

    def run_checkins(
        self,
        session: Any,
        *,
        force: bool,
        role_keys: set[RoleKey] | None,
    ) -> CheckinRunOutcome:
        roles = list_roles(session)
        if role_keys is not None:
            roles = [
                r
                for r in roles
                if matches_role_filter(r.game_code, r.uid, role_keys)
            ]
        if not roles:
            return CheckinRunOutcome(
                session=session,
                early_response={
                    "skipped": False,
                    "ok": False,
                    "summary": _EMPTY_ROLES_MSG,
                    "results": [],
                },
            )

        results: list[CheckinResult] = []
        for role in roles:
            if not force:
                probed = query_role_today(session, role)
                if is_success_status(probed.status):
                    if role.game_code == GAME_ARKNIGHTS:
                        # 跳过执行时仍按「只写 award」落库，避免查询态 message 进执行记录
                        results.append(
                            CheckinResult(
                                game_code=probed.game_code,
                                game_name=probed.game_name,
                                role_uid=probed.role_uid,
                                role_name=probed.role_name,
                                channel_name=probed.channel_name,
                                status=probed.status,
                                message=probed.awards_text or "",
                                awards_text=probed.awards_text,
                                awards=probed.awards,
                            )
                        )
                    else:
                        results.append(probed)
                    continue
            try:
                result = checkin_role(session, role)
            except SklandApiError as exc:
                msg = exc.message or ""
                already = "请勿重复签到" in msg or "重复签到" in msg
                if already:
                    # B 服方舟：GET records 常空，重复签到不再回源补奖
                    if role.game_code == GAME_ARKNIGHTS and _is_arknights_bilibili(
                        role
                    ):
                        result = CheckinResult(
                            game_code=role.game_code,
                            game_name=role.game_name,
                            role_uid=role.uid,
                            role_name=role.role_name,
                            channel_name=role.channel_name,
                            status="already",
                            message="",
                            awards_text=None,
                            awards=None,
                        )
                    else:
                        result = query_role_today(session, role)
                        if result.status == "pending":
                            result = CheckinResult(
                                game_code=role.game_code,
                                game_name=role.game_name,
                                role_uid=role.uid,
                                role_name=role.role_name,
                                channel_name=role.channel_name,
                                status="already",
                                message=(
                                    (result.awards_text or "")
                                    if role.game_code == GAME_ARKNIGHTS
                                    else "今日已签到"
                                ),
                                awards_text=result.awards_text,
                                awards=result.awards,
                            )
                        elif (
                            role.game_code == GAME_ARKNIGHTS
                            and is_success_status(result.status)
                        ):
                            # 方舟执行落库只保留 award
                            result = CheckinResult(
                                game_code=result.game_code,
                                game_name=result.game_name,
                                role_uid=result.role_uid,
                                role_name=result.role_name,
                                channel_name=result.channel_name,
                                status=result.status,
                                message=result.awards_text or "",
                                awards_text=result.awards_text,
                                awards=result.awards,
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
        return CheckinRunOutcome(session=session, results=results)

    def after_checkin(
        self, db: Session, bind: SklandBind, results: list[CheckinResult]
    ) -> None:
        ak_uids = [
            r.role_uid
            for r in results
            if r.game_code == GAME_ARKNIGHTS and is_success_status(r.status)
        ]
        if ak_uids:
            invalidate_arknights_attendance_raws(
                db, bind.member_id, uids=ak_uids
            )
        ef_uids = [
            r.role_uid
            for r in results
            if r.game_code == GAME_ENDFIELD and is_success_status(r.status)
        ]
        if ef_uids:
            invalidate_endfield_attendance_raws(db, bind.member_id, uids=ef_uids)

    def friendly_error(self, message: str) -> str:
        return friendly_error_message(message)

    def prepare_cached_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult] | None:
        from app.services.skland.awards import (
            arknights_result_needs_award_icons,
            enrich_arknights_award_icons,
        )

        need_icons = False
        for r in results:
            if r.game_code == GAME_ARKNIGHTS and r.awards:
                r.awards = enrich_arknights_award_icons(r.awards)
            if arknights_result_needs_award_icons(r):
                need_icons = True
        if need_icons:
            return None
        for r in results:
            if r.game_code == GAME_ENDFIELD:
                r.channel_name = localize_endfield_server_name(r.channel_name)
            elif r.game_code == GAME_ARKNIGHTS:
                r.channel_name = localize_arknights_channel_name(r.channel_name)
        return sort_skland_results(results)

    def normalize_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult]:
        return sort_skland_results(results)


skland_adapter = SklandCheckinAdapter()


def query_today_for_bind(
    db: Session, bind: SklandBind, *, force: bool = False
) -> dict[str, Any]:
    """今日签到状态（编排层）。

    用户展示路径应传 force=True（打开页始终回源官方）；force=False 时调度可读今日
    logs 成功态短路。方舟已签但缺结构化奖励图标时，prepare_cached_results 会强制回源补全。

    缓存 cred 失效但 hg token 仍可用时：清缓存并强制换票重试一次。
    """
    try:
        return _orch_query_today(skland_adapter, db, bind, force=force)
    except SklandApiError as exc:
        if not _looks_like_skland_auth_error(exc.message):
            raise
        from app.services.skland.session_cache import invalidate_skland_session

        invalidate_skland_session(bind.member_id)
        _session_for_bind(bind, bypass_cache=True)
        return _orch_query_today(skland_adapter, db, bind, force=True)


def run_checkin_for_bind(
    db: Session,
    bind: SklandBind,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """手动 / 自动签到；结果写入今日签到日志。

    role_keys: 仅签这些 (game_code, role_uid)；None 表示全部（手动立即签到）。
    """
    return _orch_run_checkin(
        skland_adapter, db, bind, force=force, role_keys=role_keys
    )


def run_checkin_for_member(
    db: Session,
    member: Member,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise SklandApiError("尚未绑定森空岛")
    return run_checkin_for_bind(db, bind, force=force, role_keys=role_keys)


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    _orch_job_wrapper(skland_adapter, due_only=due_only, member_id=member_id)
