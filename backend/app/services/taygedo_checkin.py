"""塔吉多绑定与每日签到编排。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive, today
from app.models.member import Member
from app.models.taygedo import TaygedoAttendanceRaw, TaygedoBind, TaygedoCheckinLog
from app.services.checkin_adapter import (
    CheckinAdapterBase,
    CheckinRunOutcome,
    SkipPolicy,
)
from app.services.checkin_common import CheckinResult, is_success_status
from app.services.checkin_orchestrator import (
    checkin_job_wrapper as _orch_job_wrapper,
)
from app.services.checkin_orchestrator import (
    query_today_for_bind as _orch_query_today,
)
from app.services.checkin_orchestrator import (
    run_checkin_for_bind as _orch_run_checkin,
)
from app.services.checkin_orchestrator import (
    run_checkin_job as _orch_run_job,
)
from app.services.checkin_role_prefs import (
    PLATFORM_TAYGEDO,
    RoleKey,
    matches_role_filter,
)
from app.services.taygedo_calendar import parse_taygedo_attendance_calendar
from app.services.taygedo_client import (
    GAME_APP,
    GAME_APP_NAME,
    GAME_HT,
    GAME_HT_NAME,
    GAME_NTE,
    GAME_NTE_NAME,
    TaygedoApiError,
    TaygedoCredentials,
    TaygedoRole,
    checkin_target,
    exchange_shop_goods,
    friendly_error_message,
    get_user_coin_state,
    list_all_game_roles,
    list_shop_goods,
    login_with_password,
    login_with_sms,
    mask_phone,
    query_today_all as taygedo_query_today_all,
    refresh_access_token,
    sort_taygedo_results,
)

logger = logging.getLogger(__name__)

JOB_KEY = "taygedo_checkin"

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
    """探测可加入角色：社区账号 + 异环 / 幻塔游戏角色。"""
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

    out: list[dict[str, str]] = [
        {
            "game_code": GAME_APP,
            "game_name": GAME_APP_NAME,
            "uid": working.uid,
            "role_name": "社区账号",
            "channel_name": "社区",
        }
    ]
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


_CALENDAR_GAMES = frozenset({GAME_NTE, GAME_HT})
_GAME_NAMES = {
    GAME_NTE: GAME_NTE_NAME,
    GAME_HT: GAME_HT_NAME,
}


def _session_for_bind(db: Session, bind: TaygedoBind) -> TaygedoCredentials:
    from app.services.taygedo_client import ensure_session

    creds = _load_creds(bind)
    working = ensure_session(creds)
    if (
        working.access_token != creds.access_token
        or working.refresh_token != creds.refresh_token
    ):
        _save_creds(bind, working)
        db.commit()
    return working


def fetch_exchange_shop(
    db: Session, member: Member, *, tab: str | None = None
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
    working = _session_for_bind(db, bind)
    goods, tabs = list_shop_goods(working, tab=str(tab or "all").strip() or "all")
    coin_state: dict[str, Any] = {}
    try:
        coin_state = get_user_coin_state(working)
    except TaygedoApiError:
        pass
    try:
        gold = int(coin_state.get("total") or 0)
    except (TypeError, ValueError):
        gold = 0
    try:
        today_get = int(coin_state.get("todayGet") or 0)
    except (TypeError, ValueError):
        today_get = 0
    try:
        today_total = int(coin_state.get("todayTotal") or 0)
    except (TypeError, ValueError):
        today_total = 0
    roles = list_all_game_roles(working)
    _save_creds(bind, working)
    db.commit()
    return {
        "gold": gold,
        "today_get": today_get,
        "today_total": today_total,
        "tabs": tabs,
        "items": [item.to_dict() for item in goods],
        "roles": [
            {
                "game_id": r.game_code,
                "game_name": r.game_name or _GAME_NAMES.get(r.game_code, r.game_code),
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
    goods_id: str,
    game_id: str,
    role_id: str,
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
    working = _session_for_bind(db, bind)
    goods_id = str(goods_id or "").strip()
    game_id = str(game_id or "").strip()
    role_id = str(role_id or "").strip()
    if not goods_id or not game_id or not role_id:
        raise TaygedoApiError("兑换参数不完整")

    shop_items, _tabs = list_shop_goods(working, tab="all", count=50)
    target = next((i for i in shop_items if i.goods_id == goods_id), None)
    if target is None:
        raise TaygedoApiError("兑换物品不存在或已下架")
    if not target.can_exchange:
        raise TaygedoApiError("该商品当前不可兑换")

    roles = list_all_game_roles(working)
    role = next(
        (
            r
            for r in roles
            if r.role_id == role_id and str(r.game_code) == game_id
        ),
        None,
    )
    if role is None:
        raise TaygedoApiError("角色不在当前塔吉多绑定列表中")

    coin_before = get_user_coin_state(working)
    try:
        gold_before = int(coin_before.get("total") or 0)
    except (TypeError, ValueError):
        gold_before = 0
    if gold_before < target.price:
        raise TaygedoApiError(
            f"塔塔币不足（需要 {target.price}，当前 {gold_before}）"
        )

    exchange_shop_goods(
        working,
        goods_id=target.goods_id,
        game_id=game_id,
        role_id=role_id,
    )
    coin_after = get_user_coin_state(working)
    try:
        gold_after = int(coin_after.get("total") or 0)
    except (TypeError, ValueError):
        gold_after = None
    _save_creds(bind, working)
    db.commit()
    return {
        "ok": True,
        "message": f"已兑换 {target.name}，请到游戏或社区查看",
        "gold": gold_after,
        "item": target.to_dict(),
    }


class TaygedoCheckinAdapter(CheckinAdapterBase):
    platform = PLATFORM_TAYGEDO
    job_key = JOB_KEY
    bind_model = TaygedoBind
    log_model = TaygedoCheckinLog
    api_error_cls = TaygedoApiError
    empty_message = "未执行任何签到"
    # 即使今日已签，仍补跑社区每日任务
    skip_policy = SkipPolicy.ALWAYS_RUN

    def get_bind(self, db: Session, member_id: int) -> TaygedoBind | None:
        return get_bind_for_member(db, member_id)

    def load_session(self, db: Session, bind: TaygedoBind) -> TaygedoCredentials:
        return _load_creds(bind)

    def save_session(
        self, db: Session, bind: TaygedoBind, session: TaygedoCredentials
    ) -> None:
        _save_creds(bind, session)

    def query_today_all(
        self, session: TaygedoCredentials
    ) -> tuple[TaygedoCredentials, list[CheckinResult]]:
        return taygedo_query_today_all(session)

    def prepare_cached_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult] | None:
        return sort_taygedo_results(results)

    def normalize_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult]:
        return sort_taygedo_results(results)

    def run_checkins(
        self,
        session: TaygedoCredentials,
        *,
        force: bool,
        role_keys: set[RoleKey] | None,
    ) -> CheckinRunOutcome:
        from app.services.taygedo_client import list_checkin_targets

        working, targets = list_checkin_targets(session)

        if role_keys is not None:
            filtered = []
            for game_code, role in targets:
                role_uid = role.role_id if role else working.uid
                if matches_role_filter(game_code, role_uid, role_keys):
                    filtered.append((game_code, role))
            targets = filtered

        if not targets:
            return CheckinRunOutcome(
                session=working,
                early_response={
                    "skipped": False,
                    "ok": False,
                    "summary": "未找到可签到目标",
                    "results": [],
                },
            )

        live_working, live_results = taygedo_query_today_all(working)
        working = live_working
        live_map = {(r.game_code, r.role_uid): r for r in live_results}

        results: list[CheckinResult] = []
        for game_code, role in targets:
            role_uid = role.role_id if role else working.uid
            probed = live_map.get((game_code, role_uid))
            # 社区 APP 即使已签也走 checkin_target，以补跑每日任务
            if (
                not force
                and game_code != GAME_APP
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
                        result = checkin_target(
                            working, game_code=game_code, role=role
                        )
                    except TaygedoApiError as exc2:
                        result = _taygedo_error_result(
                            game_code, role, role_uid, exc2.message or ""
                        )
                    else:
                        results.append(result)
                        continue
                else:
                    result = _taygedo_error_result(
                        game_code, role, role_uid, exc.message or ""
                    )
            except Exception as exc:  # noqa: BLE001
                logger.exception("taygedo checkin unexpected error")
                result = _taygedo_error_result(
                    game_code, role, role_uid, str(exc)
                )
            results.append(result)

        return CheckinRunOutcome(session=working, results=results)

    def after_checkin(
        self, db: Session, bind: TaygedoBind, results: list[CheckinResult]
    ) -> None:
        cal_uids = [
            r.role_uid
            for r in results
            if r.game_code in _CALENDAR_GAMES and is_success_status(r.status)
        ]
        if cal_uids:
            invalidate_taygedo_attendance_raws(
                db, bind.member_id, role_uids=cal_uids
            )

    def enrich_summary(self, summary: str, results: list[CheckinResult]) -> str:
        extra_parts = [
            r.extra_text
            for r in results
            if r.extra_text and r.game_code == GAME_APP
        ]
        if not extra_parts:
            return summary
        return f"{summary}\n" + "\n".join(extra_parts)

    def friendly_error(self, message: str) -> str:
        return friendly_error_message(message)


def _taygedo_error_result(
    game_code: str,
    role: TaygedoRole | None,
    role_uid: str,
    msg: str,
) -> CheckinResult:
    already = any(k in msg for k in ("已签到", "重复签到", "签到过", "already"))
    if role is not None:
        game_name = role.game_name
        role_name = role.role_name
        channel = role.game_name
    elif game_code == GAME_APP:
        game_name = GAME_APP_NAME
        role_name = "社区账号"
        channel = "社区"
    else:
        game_name = game_code
        role_name = "-"
        channel = game_code
    return CheckinResult(
        game_code=game_code,
        game_name=game_name,
        role_uid=role_uid,
        role_name=role_name,
        channel_name=channel,
        status="already" if already else "error",
        message=("今日已签到" if already else friendly_error_message(msg)),
    )


taygedo_adapter = TaygedoCheckinAdapter()


def query_today_for_bind(
    db: Session, bind: TaygedoBind, *, force: bool = False
) -> dict[str, Any]:
    """今日签到状态：HTTP 展示路径 force 默认 true，始终查官方并落库。"""
    return _orch_query_today(taygedo_adapter, db, bind, force=force)


def query_today_for_member(
    db: Session, member: Member, *, force: bool = False
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise TaygedoApiError("尚未绑定塔吉多")
    return query_today_for_bind(db, bind, force=force)


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
    return _orch_run_checkin(
        taygedo_adapter, db, bind, force=force, role_keys=role_keys
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
        raise TaygedoApiError("尚未绑定塔吉多")
    return run_checkin_for_bind(db, bind, force=force, role_keys=role_keys)


def run_taygedo_checkin_job(
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    return _orch_run_job(
        taygedo_adapter, db, due_only=due_only, member_id=member_id
    )


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    _orch_job_wrapper(taygedo_adapter, due_only=due_only, member_id=member_id)
