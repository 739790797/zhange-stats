"""追放社区绑定与每日签到编排。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive
from app.models.exilium import ExiliumBind, ExiliumCheckinLog
from app.models.member import Member
from app.services.checkin.adapter import (
    CheckinAdapterBase,
    CheckinRunOutcome,
    SkipPolicy,
)
from app.services.checkin.binding import after_bind, unbind_member
from app.services.checkin.common import CheckinResult
from app.services.checkin.credentials import (
    StoredCreds,
    refresh_creds_locked,
    store_creds_if_changed,
)
from app.services.checkin.orchestrator import (
    query_today_for_bind as _orch_query_today,
)
from app.services.checkin.orchestrator import (
    run_checkin_for_bind as _orch_run_checkin,
)
from app.services.checkin.role_prefs import (
    PLATFORM_EXILIUM,
    RoleKey,
    matches_role_filter,
)
from app.services.exilium.attendance import (
    checkin,
    ensure_session,
    query_today,
)
from app.services.exilium.client import (
    GAME_CODE,
    ExiliumApiError,
    ExiliumCredentials,
    exchange_item,
    friendly_error_message,
    get_user_score,
    list_exchange_items,
    list_score_logs,
    login_with_password,
    login_with_sms,
    mask_account,
)

logger = logging.getLogger(__name__)

JOB_KEY = "exilium_checkin"


def get_bind_for_member(db: Session, member_id: int) -> ExiliumBind | None:
    return db.query(ExiliumBind).filter(ExiliumBind.member_id == member_id).one_or_none()


def _load_payload(bind: ExiliumBind) -> dict[str, Any]:
    raw = decrypt_secret(bind.credentials_enc)
    if not raw:
        raise ExiliumApiError("凭证已损坏，请重新绑定")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExiliumApiError("凭证格式无效，请重新绑定") from exc
    if not isinstance(payload, dict):
        raise ExiliumApiError("凭证格式无效，请重新绑定")
    return payload


def _load_creds(bind: ExiliumBind) -> ExiliumCredentials:
    return ExiliumCredentials.from_dict(_load_payload(bind))


def _drop_plaintext_password(db: Session, bind: ExiliumBind) -> None:
    """早期凭证里存的是明文口令：用到时改写成只带 MD5（按读出时的密文 CAS，期间被改过就留给下次）。"""
    payload = _load_payload(bind)
    if "password" not in payload:
        return
    creds = ExiliumCredentials.from_dict(payload)
    stored = StoredCreds(creds=creds, loaded_enc=bind.credentials_enc or "", loaded=payload)
    store_creds_if_changed(db, bind, stored, extra=_creds_columns(creds))
    db.commit()


def _creds_columns(creds: ExiliumCredentials) -> dict[str, Any]:
    return {"phone_mask": mask_account(creds.account_name) or creds.nickname}


def _save_creds(bind: ExiliumBind, creds: ExiliumCredentials) -> None:
    bind.credentials_enc = encrypt_secret(json.dumps(creds.to_dict(), ensure_ascii=False))
    bind.phone_mask = _creds_columns(creds)["phone_mask"]
    bind.updated_at = now_naive()


def _store_creds(
    db: Session, bind: ExiliumBind, stored: StoredCreds[ExiliumCredentials]
) -> None:
    store_creds_if_changed(db, bind, stored, extra=_creds_columns(stored.creds))


def bind_with_password(db: Session, member: Member, account: str, password: str) -> ExiliumBind:
    creds = login_with_password(account, password)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = ExiliumBind(member_id=member.id, credentials_enc="", auto_checkin=False)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    after_bind(exilium_adapter, db, bind)
    return bind


def bind_with_sms(db: Session, member: Member, phone: str, captcha: str) -> ExiliumBind:
    creds = login_with_sms(phone, captcha)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        bind = ExiliumBind(member_id=member.id, credentials_enc="", auto_checkin=False)
        db.add(bind)
    _save_creds(bind, creds)
    db.commit()
    db.refresh(bind)
    after_bind(exilium_adapter, db, bind)
    return bind


def unbind_exilium(db: Session, member: Member) -> None:
    unbind_member(exilium_adapter, db, member.id)


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> ExiliumBind:
    from app.services.checkin.schedule import clamp_checkin_hour, clamp_checkin_minute

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
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


def _session_for_bind(db: Session, bind: ExiliumBind) -> StoredCreds[ExiliumCredentials]:
    """探活；token 失效且存了口令摘要时重登。"""
    _drop_plaintext_password(db, bind)
    return refresh_creds_locked(
        db,
        bind,
        platform=PLATFORM_EXILIUM,
        load=_load_creds,
        refresh=ensure_session,
        extra=_creds_columns,
    )


def preview_roles(db: Session, member: Member) -> list[dict[str, str]]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    working = _session_for_bind(db, bind).creds
    return [
        {
            "game_code": "exilium_bbs",
            "game_name": "追放社区",
            "uid": working.user_id or working.account_name or "-",
            "role_name": working.nickname
            or mask_account(working.account_name)
            or "社区账号",
            "channel_name": "社区",
        }
    ]


def fetch_exchange_shop(db: Session, member: Member) -> dict[str, Any]:
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise ExiliumApiError("尚未绑定追放社区")
    working = _session_for_bind(db, bind).creds
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
    working = _session_for_bind(db, bind).creds
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
    working = _session_for_bind(db, bind).creds
    return list_score_logs(working, page=page, page_size=page_size)


class ExiliumCheckinAdapter(CheckinAdapterBase):
    platform = PLATFORM_EXILIUM
    job_key = JOB_KEY
    bind_model = ExiliumBind
    log_model = ExiliumCheckinLog
    api_error_cls = ExiliumApiError
    empty_message = "未执行签到"
    skip_policy = SkipPolicy.ALWAYS_RUN

    def get_bind(self, db: Session, member_id: int) -> ExiliumBind | None:
        return get_bind_for_member(db, member_id)

    def load_session(
        self, db: Session, bind: ExiliumBind
    ) -> StoredCreds[ExiliumCredentials]:
        return _session_for_bind(db, bind)

    def save_session(
        self, db: Session, bind: ExiliumBind, session: StoredCreds[ExiliumCredentials]
    ) -> None:
        _store_creds(db, bind, session)

    def query_today_all(
        self, session: StoredCreds[ExiliumCredentials]
    ) -> tuple[StoredCreds[ExiliumCredentials], list[CheckinResult]]:
        working, results = query_today(session.creds, session_checked=True)
        return session.with_creds(working), results

    def run_checkins(
        self,
        session: StoredCreds[ExiliumCredentials],
        *,
        force: bool,
        role_keys: set[RoleKey] | None,
    ) -> CheckinRunOutcome:
        expected_uid = session.creds.user_id or session.creds.account_name or "-"
        if role_keys is not None and not matches_role_filter(
            GAME_CODE, expected_uid, role_keys
        ):
            return CheckinRunOutcome(
                session=session,
                early_response={
                    "skipped": True,
                    "ok": True,
                    "reason": "role_filtered",
                    "summary": "当前时间无需签到该角色",
                    "results": [],
                },
            )
        # 即使今日已签，仍走 checkin：会补跑每日任务（浏览/点赞/分享）
        working, results = checkin(session.creds, force=force, session_checked=True)
        return CheckinRunOutcome(session=session.with_creds(working), results=results)

    def friendly_error(self, message: str) -> str:
        return friendly_error_message(message)

    def enrich_summary(self, summary: str, results: list[CheckinResult]) -> str:
        extra_parts = [r.extra_text for r in results if r.extra_text]
        if not extra_parts:
            return summary
        return f"{summary}\n" + "\n".join(extra_parts)

    def mark_as_skipped(
        self,
        bind: ExiliumBind,
        results: list[CheckinResult],
        *,
        force: bool,
        checkin_date: Any,
    ) -> bool:
        if force or not results:
            return False
        _ = (bind, checkin_date)
        result = results[0]
        return bool(result.status == "already")


exilium_adapter = ExiliumCheckinAdapter()


def query_today_for_bind(
    db: Session, bind: ExiliumBind, *, force: bool = False
) -> dict[str, Any]:
    return _orch_query_today(exilium_adapter, db, bind, force=force)


def run_checkin_for_bind(
    db: Session,
    bind: ExiliumBind,
    *,
    force: bool = False,
    role_keys: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    return _orch_run_checkin(
        exilium_adapter, db, bind, force=force, role_keys=role_keys
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
        raise ExiliumApiError("尚未绑定追放社区")
    return run_checkin_for_bind(db, bind, force=force, role_keys=role_keys)
