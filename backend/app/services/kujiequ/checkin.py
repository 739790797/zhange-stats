"""库街区绑定与每日签到编排（社区 + 鸣潮/战双）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive
from app.models.kujiequ import KujiequAttendanceRaw, KujiequBind, KujiequCheckinLog
from app.models.member import Member
from app.services.checkin.adapter import (
    CheckinAdapterBase,
    CheckinRunOutcome,
    SkipPolicy,
)
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
from app.services.checkin.role_prefs import PLATFORM_KUJIEQU, RoleKey
from app.services.kujiequ.calendar import parse_kujiequ_attendance_calendar
from app.services.kujiequ.attendance import (
    friendly_error_message,
    query_today_all as kujiequ_query_today_all,
    run_all_checkins,
    sort_kujiequ_results,
)
from app.services.kujiequ.client import (
    GAME_NAMES,
    GAME_PGR,
    GAME_WW,
    GameRole,
    KujiequApiError,
    KujiequCredentials,
    exchange_commodity,
    get_total_gold,
    list_all_game_roles,
    list_commodities,
    list_roles_for_game,
    login_with_sms,
    login_with_token,
    mask_phone,
)

logger = logging.getLogger(__name__)

JOB_KEY = "kujiequ_checkin"
_CALENDAR_GAMES = frozenset({f"game_{GAME_PGR}", f"game_{GAME_WW}"})


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


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> KujiequBind:
    from app.services.checkin.schedule import clamp_checkin_hour, clamp_checkin_minute

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
    """探测可加入角色：社区账号 + 鸣潮/战双游戏角色。"""
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    creds = _load_creds(bind)
    if not creds.user_id:
        from app.services.kujiequ.client import fetch_mine

        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name
        _save_creds(bind, creds)
        db.commit()

    out: list[dict[str, str]] = [
        {
            "game_code": "kujiequ",
            "game_name": "库街区",
            "uid": creds.user_id or "community",
            "role_name": creds.user_name or "社区账号",
            "channel_name": "社区",
        }
    ]
    for r in list_all_game_roles(creds):
        out.append(
            {
                "game_code": f"game_{r.game_id}",
                "game_name": r.game_name,
                "uid": r.role_id,
                "role_name": r.role_name,
                "channel_name": r.server_name,
            }
        )
    return out


def _session_for_bind(db: Session, bind: KujiequBind) -> KujiequCredentials:
    creds = _load_creds(bind)
    if not creds.user_id:
        from app.services.kujiequ.client import fetch_mine

        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name
        _save_creds(bind, creds)
        db.commit()
    return creds


def fetch_exchange_shop(
    db: Session, member: Member, *, game_id: int | None = None
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    working = _session_for_bind(db, bind)
    items = list_commodities(working, game_id=game_id)
    gold = get_total_gold(working)
    roles = list_all_game_roles(working)
    return {
        "gold": gold,
        "items": [item.to_dict() for item in items],
        "roles": [
            {
                "game_id": r.game_id,
                "game_name": r.game_name or GAME_NAMES.get(r.game_id, f"游戏{r.game_id}"),
                "role_id": r.role_id,
                "role_name": r.role_name,
            }
            for r in roles
        ],
    }


def run_exchange_for_member(
    db: Session,
    member: Member,
    *,
    commodity_code: str,
    game_id: int,
    role_id: str | None = None,
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")
    working = _session_for_bind(db, bind)
    shop = {i.commodity_code: i for i in list_commodities(working)}
    target = shop.get(str(commodity_code).strip())
    if target is None:
        raise KujiequApiError("兑换物品不存在或已下架")
    if not target.can_exchange:
        if target.commodity_type == 2:
            raise KujiequApiError("实物商品请在库街区 App 兑换（需地址与验证）")
        raise KujiequApiError("该商品当前不可兑换")
    gid = int(game_id if game_id is not None else target.game_id)
    if target.game_id and gid != int(target.game_id):
        raise KujiequApiError("商品与游戏不匹配")
    rid = str(role_id or "").strip()
    if gid in (GAME_PGR, GAME_WW):
        if not rid:
            raise KujiequApiError("请选择接收角色")
        roles = list_all_game_roles(working)
        role = next(
            (r for r in roles if r.role_id == rid and int(r.game_id) == gid),
            None,
        )
        if role is None:
            raise KujiequApiError("角色不在当前库街区绑定列表中")
    gold_before = get_total_gold(working)
    if gold_before < target.commodity_price:
        raise KujiequApiError(
            f"库洛币不足（需要 {target.commodity_price}，当前 {gold_before}）"
        )
    exchange_commodity(
        working,
        commodity_code=target.commodity_code,
        game_id=gid,
        role_id=rid or None,
    )
    gold_after = get_total_gold(working)
    return {
        "ok": True,
        "message": f"已兑换 {target.commodity_name}，请到游戏或社区查看",
        "gold": gold_after,
        "item": target.to_dict(),
    }


class KujiequCheckinAdapter(CheckinAdapterBase):
    platform = PLATFORM_KUJIEQU
    job_key = JOB_KEY
    bind_model = KujiequBind
    log_model = KujiequCheckinLog
    api_error_cls = KujiequApiError
    empty_message = "未执行任何签到"
    # 即使今日已签，仍补跑社区每日任务
    skip_policy = SkipPolicy.ALWAYS_RUN

    def get_bind(self, db: Session, member_id: int) -> KujiequBind | None:
        return get_bind_for_member(db, member_id)

    def load_session(self, db: Session, bind: KujiequBind) -> KujiequCredentials:
        return _load_creds(bind)

    def save_session(
        self, db: Session, bind: KujiequBind, session: KujiequCredentials
    ) -> None:
        _save_creds(bind, session)

    def query_today_all(
        self, session: KujiequCredentials
    ) -> tuple[KujiequCredentials, list[CheckinResult]]:
        return kujiequ_query_today_all(session)

    def run_checkins(
        self,
        session: KujiequCredentials,
        *,
        force: bool,
        role_keys: set[RoleKey] | None,
    ) -> CheckinRunOutcome:
        _ = force
        working, results = run_all_checkins(session, role_keys=role_keys)
        return CheckinRunOutcome(session=working, results=results)

    def prepare_cached_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult] | None:
        return sort_kujiequ_results(results)

    def normalize_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult]:
        return sort_kujiequ_results(results)

    def friendly_error(self, message: str) -> str:
        return friendly_error_message(message)

    def after_checkin(
        self, db: Session, bind: KujiequBind, results: list[CheckinResult]
    ) -> None:
        cal_uids = [
            r.role_uid
            for r in results
            if r.game_code in _CALENDAR_GAMES and is_success_status(r.status)
        ]
        if cal_uids:
            invalidate_kujiequ_attendance_raws(
                db, bind.member_id, role_uids=cal_uids
            )

    def enrich_summary(self, summary: str, results: list[CheckinResult]) -> str:
        extra_parts = [
            r.extra_text
            for r in results
            if r.extra_text and r.game_code == "kujiequ"
        ]
        if not extra_parts:
            return summary
        return f"{summary}\n" + "\n".join(extra_parts)

    def mark_as_skipped(
        self,
        bind: KujiequBind,
        results: list[CheckinResult],
        *,
        force: bool,
        checkin_date: Any,
    ) -> bool:
        if force or not results:
            return False
        community = next((r for r in results if r.game_code == "kujiequ"), None)
        if community is None:
            return False
        _ = (bind, checkin_date)
        return bool(community.status == "already")


kujiequ_adapter = KujiequCheckinAdapter()


def invalidate_kujiequ_attendance_raws(
    db: Session,
    member_id: int,
    *,
    game_code: str | None = None,
    role_uids: list[str] | None = None,
) -> None:
    """签到成功后丢弃日历 raw，下次打开页回源。"""
    q = db.query(KujiequAttendanceRaw).filter(
        KujiequAttendanceRaw.member_id == member_id
    )
    if game_code:
        q = q.filter(KujiequAttendanceRaw.game_code == game_code)
    if role_uids:
        q = q.filter(KujiequAttendanceRaw.role_uid.in_(role_uids))
    q.delete(synchronize_session=False)


def _kujiequ_today_log_hint(
    db: Session, *, member_id: int, game_code: str, role_uid: str
) -> bool:
    from app.core.timeutil import today as beijing_today
    from app.services.checkin.common import is_success_status as _ok

    day = beijing_today()
    row = (
        db.query(KujiequCheckinLog)
        .filter(
            KujiequCheckinLog.member_id == member_id,
            KujiequCheckinLog.checkin_date == day,
            KujiequCheckinLog.game_code == game_code,
            KujiequCheckinLog.role_uid == role_uid,
        )
        .one_or_none()
    )
    return bool(row and _ok(row.status))


def get_kujiequ_attendance_calendar_for_member(
    db: Session,
    member: Member,
    *,
    game_code: str,
    role_uid: str | None = None,
    force: bool = False,
) -> tuple[dict[str, Any], GameRole, list[GameRole], Any, bool]:
    """读库二次加工鸣潮/战双签到日历；无记录、跨月或 force 时回源落库。"""
    from datetime import datetime

    from app.core.timeutil import BEIJING, now as beijing_now
    from app.services.kujiequ.attendance import fetch_game_attendance_bundle
    from app.services.raw_payload_monitor import note_raw_payload

    game_code = str(game_code or "").strip()
    if game_code not in _CALENDAR_GAMES:
        raise KujiequApiError("仅鸣潮 / 战双支持签到日历")
    try:
        game_id = int(game_code.removeprefix("game_"))
    except ValueError as exc:
        raise KujiequApiError("无效的游戏代码") from exc

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise KujiequApiError("尚未绑定库街区")

    working = _session_for_bind(db, bind)
    game_name = GAME_NAMES.get(game_id, f"游戏{game_id}")
    try:
        roles = list_roles_for_game(working, game_id)
    except KujiequApiError as exc:
        raise KujiequApiError(friendly_error_message(exc.message)) from exc
    _save_creds(bind, working)
    db.commit()

    if not roles:
        raise KujiequApiError(f"未找到{game_name}绑定角色")

    target_uid = str(role_uid or "").strip()
    role = (
        next((r for r in roles if r.role_id == target_uid), None)
        if target_uid
        else roles[0]
    )
    if role is None:
        raise KujiequApiError("角色不在当前库街区绑定列表中")

    row = (
        db.query(KujiequAttendanceRaw)
        .filter(
            KujiequAttendanceRaw.member_id == member.id,
            KujiequAttendanceRaw.game_code == game_code,
            KujiequAttendanceRaw.role_uid == role.role_id,
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
            bundle = fetch_game_attendance_bundle(working, role)
            raw_json = json.dumps(bundle, ensure_ascii=False)
            note_raw_payload(
                "kujiequ_attendance_raw",
                raw_json,
                member_id=member.id,
                uid=role.role_id,
            )
            synced = now_naive()
            if row is None:
                row = KujiequAttendanceRaw(
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
        except KujiequApiError as exc:
            if row is None:
                raise KujiequApiError(friendly_error_message(exc.message)) from exc
            stale = True
            logger.warning(
                "kujiequ attendance refresh failed member_id=%s game=%s role=%s: %s",
                member.id,
                game_code,
                role.role_id,
                exc.message,
            )

    try:
        resp = json.loads(row.raw_json)
    except json.JSONDecodeError as exc:
        raise KujiequApiError("签到日历数据损坏，请刷新重试") from exc
    if not isinstance(resp, dict):
        raise KujiequApiError("签到日历数据格式异常，请刷新重试")

    log_today = _kujiequ_today_log_hint(
        db, member_id=member.id, game_code=game_code, role_uid=role.role_id
    )
    parsed = parse_kujiequ_attendance_calendar(
        resp,
        fallback_has_today=True if log_today else None,
    )
    return parsed, role, roles, row.synced_at, stale


def query_today_for_bind(
    db: Session, bind: KujiequBind, *, force: bool = False
) -> dict[str, Any]:
    return _orch_query_today(kujiequ_adapter, db, bind, force=force)


def run_checkin_for_bind(
    db: Session,
    bind: KujiequBind,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    return _orch_run_checkin(
        kujiequ_adapter, db, bind, force=force, role_keys=role_keys
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
        raise KujiequApiError("尚未绑定库街区")
    return run_checkin_for_bind(db, bind, force=force, role_keys=role_keys)


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    _orch_job_wrapper(kujiequ_adapter, due_only=due_only, member_id=member_id)
