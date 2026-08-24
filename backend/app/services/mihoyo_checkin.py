"""米游社绑定与每日签到编排。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive
from app.models.member import Member
from app.models.mihoyo import MihoyoBind, MihoyoCheckinLog
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
from app.services.checkin_role_prefs import PLATFORM_MIHOYO, RoleKey
from app.services.mihoyo_attendance import (
    GAME_CODE,
    query_today_all as mihoyo_query_today_all,
    run_all_checkins,
    sort_mihoyo_results,
)
from app.services.mihoyo_auth import (
    MihoyoNeedGeetest,
    login_with_password,
    login_with_sms,
    send_login_sms,
)
from app.services.mihoyo_client import (
    MihoyoApiError,
    MihoyoCredentials,
    bind_with_cookie,
    exchange_goods,
    friendly_error_message,
    get_points_balance,
    list_exchange_goods,
    list_game_roles,
    list_points_logs,
    mask_account,
)

logger = logging.getLogger(__name__)

JOB_KEY = "mihoyo_checkin"


def get_bind_for_member(db: Session, member_id: int) -> MihoyoBind | None:
    return db.query(MihoyoBind).filter(MihoyoBind.member_id == member_id).one_or_none()


def _load_creds(bind: MihoyoBind) -> MihoyoCredentials:
    raw = decrypt_secret(bind.credentials_enc)
    if not raw:
        raise MihoyoApiError("凭证已损坏，请重新绑定")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MihoyoApiError("凭证格式无效，请重新绑定") from exc
    if not isinstance(payload, dict):
        raise MihoyoApiError("凭证格式无效，请重新绑定")
    return MihoyoCredentials.from_dict(payload)


def _save_creds(bind: MihoyoBind, creds: MihoyoCredentials) -> None:
    bind.credentials_enc = encrypt_secret(json.dumps(creds.to_dict(), ensure_ascii=False))
    bind.phone_mask = mask_account(creds.stuid or creds.ltuid) or creds.nickname
    bind.updated_at = now_naive()


def bind_member_with_creds(
    db: Session, member: Member, creds: MihoyoCredentials
) -> MihoyoBind:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = MihoyoBind(member_id=member.id, credentials_enc="", auto_checkin=False)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    _maybe_checkin_after_bind(db, bind)
    return bind


def bind_member_with_cookie(db: Session, member: Member, cookie: str) -> MihoyoBind:
    return bind_member_with_creds(db, member, bind_with_cookie(cookie))


def bind_member_with_sms(
    db: Session, member: Member, phone: str, captcha: str
) -> MihoyoBind:
    return bind_member_with_creds(db, member, login_with_sms(phone, captcha))


def bind_member_with_password(
    db: Session,
    member: Member,
    account: str,
    password: str,
    *,
    geetest: str | None = None,
    mmt_key: str | None = None,
) -> MihoyoBind:
    return bind_member_with_creds(
        db,
        member,
        login_with_password(account, password, geetest=geetest, mmt_key=mmt_key),
    )


def send_sms_for_bind(
    phone: str,
    *,
    geetest: str | None = None,
    mmt_key: str | None = None,
) -> dict[str, Any]:
    try:
        return send_login_sms(phone, geetest=geetest, mmt_key=mmt_key)
    except MihoyoNeedGeetest as exc:
        return {
            "ok": False,
            "need_geetest": True,
            "captcha_id": exc.captcha_id,
            "mmt_key": exc.mmt_key,
            "message": exc.message,
        }


def _maybe_checkin_after_bind(db: Session, bind: MihoyoBind) -> None:
    if not bind.auto_checkin:
        return
    try:
        run_checkin_for_bind(db, bind, force=False)
    except Exception:  # noqa: BLE001
        logger.exception("mihoyo checkin after bind failed member_id=%s", bind.member_id)
        db.rollback()
        db.refresh(bind)


def unbind_mihoyo(db: Session, member: Member) -> None:
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
) -> MihoyoBind:
    from app.services.checkin_schedule import clamp_checkin_hour, clamp_checkin_minute

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise MihoyoApiError("尚未绑定米游社")
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


def _session_for_bind(db: Session, bind: MihoyoBind) -> MihoyoCredentials:
    from app.services.mihoyo_client import ensure_session

    creds = _load_creds(bind)
    working = ensure_session(creds)
    if working.to_dict() != creds.to_dict():
        _save_creds(bind, working)
        db.commit()
    return working


def preview_roles(db: Session, member: Member) -> list[dict[str, str]]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise MihoyoApiError("尚未绑定米游社")
    working = _session_for_bind(db, bind)
    roles: list[dict[str, str]] = [
        {
            "game_code": GAME_CODE,
            "game_name": "米游社",
            "uid": working.stuid or working.ltuid or "-",
            "role_name": working.nickname or mask_account(working.stuid) or "社区账号",
            "channel_name": "社区",
        }
    ]
    try:
        game_roles = list_game_roles(working)
    except MihoyoApiError as exc:
        logger.warning("mihoyo preview_roles list_game_roles: %s", exc.message)
        game_roles = []
    for role in game_roles:
        roles.append(
            {
                "game_code": role.game_code,
                "game_name": role.game_name,
                "uid": role.role_uid,
                "role_name": role.role_name,
                "channel_name": role.channel_name,
            }
        )
    return roles


def fetch_exchange_shop(db: Session, member: Member) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise MihoyoApiError("尚未绑定米游社")
    working = _session_for_bind(db, bind)
    items = list_exchange_goods(working)
    points = get_points_balance(working)
    return {
        "points": points,
        "items": [item.to_dict() for item in items],
    }


def run_exchange_for_member(
    db: Session,
    member: Member,
    *,
    goods_id: str,
    game_biz: str = "",
    region: str = "",
    role_uid: str = "",
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise MihoyoApiError("尚未绑定米游社")
    working = _session_for_bind(db, bind)
    shop = {i.goods_id: i for i in list_exchange_goods(working)}
    target = shop.get(str(goods_id).strip())
    if target is None:
        raise MihoyoApiError("兑换物品不存在或已下架")
    points_before = get_points_balance(working)
    if points_before < target.price:
        raise MihoyoApiError(f"米游币不足（需要 {target.price}，当前 {points_before}）")
    exchange_goods(
        working,
        goods_id=target.goods_id,
        game_biz=game_biz or target.game_biz,
        region=region,
        role_uid=role_uid,
    )
    points_after = get_points_balance(working)
    return {
        "ok": True,
        "message": f"已兑换 {target.goods_name}，请到游戏或社区查看",
        "points": points_after,
        "item": target.to_dict(),
    }


def fetch_points_logs(
    db: Session,
    member: Member,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise MihoyoApiError("尚未绑定米游社")
    working = _session_for_bind(db, bind)
    return list_points_logs(working, page=page, page_size=page_size)


class MihoyoCheckinAdapter(CheckinAdapterBase):
    platform = PLATFORM_MIHOYO
    job_key = JOB_KEY
    bind_model = MihoyoBind
    log_model = MihoyoCheckinLog
    api_error_cls = MihoyoApiError
    empty_message = "未执行任何签到"
    skip_policy = SkipPolicy.ALWAYS_RUN

    def get_bind(self, db: Session, member_id: int) -> MihoyoBind | None:
        return get_bind_for_member(db, member_id)

    def load_session(self, db: Session, bind: MihoyoBind) -> MihoyoCredentials:
        return _load_creds(bind)

    def save_session(
        self, db: Session, bind: MihoyoBind, session: MihoyoCredentials
    ) -> None:
        _save_creds(bind, session)

    def query_today_all(
        self, session: MihoyoCredentials
    ) -> tuple[MihoyoCredentials, list[CheckinResult]]:
        return mihoyo_query_today_all(session)

    def run_checkins(
        self,
        session: MihoyoCredentials,
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
        return sort_mihoyo_results(results)

    def normalize_results(
        self, results: list[CheckinResult]
    ) -> list[CheckinResult]:
        return sort_mihoyo_results(results)

    def friendly_error(self, message: str) -> str:
        return friendly_error_message(message)

    def enrich_summary(self, summary: str, results: list[CheckinResult]) -> str:
        extra_parts = [
            r.extra_text for r in results if r.extra_text and r.game_code == GAME_CODE
        ]
        if not extra_parts:
            return summary
        return f"{summary}\n" + "\n".join(extra_parts)

    def mark_as_skipped(
        self,
        bind: MihoyoBind,
        results: list[CheckinResult],
        *,
        force: bool,
        checkin_date: Any,
    ) -> bool:
        if force or not results:
            return False
        community = next((r for r in results if r.game_code == GAME_CODE), None)
        if community is None:
            return False
        return bool(
            bind.last_checkin_date == checkin_date
            and bind.last_checkin_ok
            and community.status == "already"
            and all(
                r.status in ("already", "ok")
                for r in results
                if r.game_code != GAME_CODE and is_success_status(r.status)
            )
        )


mihoyo_adapter = MihoyoCheckinAdapter()


def query_today_for_bind(
    db: Session, bind: MihoyoBind, *, force: bool = False
) -> dict[str, Any]:
    return _orch_query_today(mihoyo_adapter, db, bind, force=force)


def run_checkin_for_bind(
    db: Session,
    bind: MihoyoBind,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    return _orch_run_checkin(
        mihoyo_adapter, db, bind, force=force, role_keys=role_keys
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
        raise MihoyoApiError("尚未绑定米游社")
    return run_checkin_for_bind(db, bind, force=force, role_keys=role_keys)


def run_mihoyo_checkin_job(
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    return _orch_run_job(
        mihoyo_adapter, db, due_only=due_only, member_id=member_id
    )


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    _orch_job_wrapper(mihoyo_adapter, due_only=due_only, member_id=member_id)
