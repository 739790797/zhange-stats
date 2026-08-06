"""库街区绑定与每日签到编排（社区 + 鸣潮/战双）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive
from app.models.kujiequ import KujiequBind, KujiequCheckinLog
from app.models.member import Member
from app.services.checkin_adapter import CheckinAdapterBase, CheckinRunOutcome
from app.services.checkin_common import CheckinResult
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
from app.services.checkin_role_prefs import PLATFORM_KUJIEQU, RoleKey
from app.services.kujiequ_client import (
    KujiequApiError,
    KujiequCredentials,
    friendly_error_message,
    list_all_game_roles,
    login_with_sms,
    login_with_token,
    mask_phone,
    query_today_all as kujiequ_query_today_all,
    run_all_checkins,
)

logger = logging.getLogger(__name__)

JOB_KEY = "kujiequ_checkin"


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


def set_auto_checkin(db: Session, member: Member, enabled: bool) -> KujiequBind:
    return update_bind_prefs(db, member, auto_checkin=bool(enabled))


def update_bind_prefs(
    db: Session,
    member: Member,
    *,
    auto_checkin: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
) -> KujiequBind:
    from app.services.checkin_schedule import clamp_checkin_hour, clamp_checkin_minute

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


class KujiequCheckinAdapter(CheckinAdapterBase):
    platform = PLATFORM_KUJIEQU
    job_key = JOB_KEY
    bind_model = KujiequBind
    log_model = KujiequCheckinLog
    api_error_cls = KujiequApiError
    empty_message = "未执行任何签到"

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

    def friendly_error(self, message: str) -> str:
        return friendly_error_message(message)


kujiequ_adapter = KujiequCheckinAdapter()


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


def run_kujiequ_checkin_job(
    db: Session,
    *,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[str, Any]:
    return _orch_run_job(
        kujiequ_adapter, db, due_only=due_only, member_id=member_id
    )


def checkin_job_wrapper(*, due_only: bool = True, member_id: int | None = None) -> None:
    _orch_job_wrapper(kujiequ_adapter, due_only=due_only, member_id=member_id)
