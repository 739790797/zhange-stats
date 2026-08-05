"""塔吉多：绑定、异环签到状态与手动/自动签到。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.platform_checkin import (
    build_checkin_response,
    build_checkin_status,
    raise_api_error,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_user_member
from app.core.platform_deps import require_feature
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    TaygedoBindJsonRequest,
    TaygedoBindPasswordRequest,
    TaygedoBindSmsRequest,
    TaygedoBindSmsSendRequest,
    TaygedoBindSmsSendResponse,
    TaygedoBindUpdate,
    TaygedoCheckinLogOut,
    TaygedoCheckinResponse,
    TaygedoCheckinResultItem,
    TaygedoRoleOut,
    TaygedoStatusOut,
)
from app.services.taygedo_checkin import (
    bind_with_credentials_json,
    bind_with_password,
    bind_with_sms,
    get_bind_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    unbind_taygedo,
    update_bind_prefs,
)
from app.services.taygedo_client import TaygedoApiError, send_sms_captcha

router = APIRouter(
    prefix="/taygedo",
    tags=["taygedo"],
    dependencies=[Depends(require_feature("taygedo"))],
)


@router.get("/status", response_model=TaygedoStatusOut)
def taygedo_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
    include_roles: bool = Query(default=True),
    force: bool = Query(default=False),
):
    bind = get_bind_for_member(db, member.id)
    return build_checkin_status(
        db=db,
        member=member,
        bind=bind,
        status_cls=TaygedoStatusOut,
        role_cls=TaygedoRoleOut,
        result_cls=TaygedoCheckinResultItem,
        query_today=query_today_for_bind,
        preview_roles=preview_roles,
        api_error_cls=TaygedoApiError,
        include_roles=include_roles,
        force=force,
        extra_fields={"phone_mask": getattr(bind, "phone_mask", None) if bind else None},
    )


@router.get("/logs", response_model=list[TaygedoCheckinLogOut])
def taygedo_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    """已弃用：签到改为实时查询，不再返回历史记录。"""
    _ = (db, user, limit)
    return []


@router.post("/bind/password", response_model=TaygedoStatusOut)
def taygedo_bind_password(
    payload: TaygedoBindPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_password(db, member, payload.phone, payload.password)
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return taygedo_status(db=db, user=user, member=member, include_roles=True)


@router.post("/bind/sms/send", response_model=TaygedoBindSmsSendResponse)
def taygedo_bind_sms_send(
    payload: TaygedoBindSmsSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = (db, user, member)
    try:
        device_id = send_sms_captcha(payload.phone, payload.device_id)
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return TaygedoBindSmsSendResponse(device_id=device_id, message="验证码已发送")


@router.post("/bind/sms", response_model=TaygedoStatusOut)
def taygedo_bind_sms(
    payload: TaygedoBindSmsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_sms(db, member, payload.phone, payload.captcha, payload.device_id)
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return taygedo_status(db=db, user=user, member=member, include_roles=True)


@router.post("/bind/json", response_model=TaygedoStatusOut)
def taygedo_bind_json(
    payload: TaygedoBindJsonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_credentials_json(db, member, payload.credentials_json)
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return taygedo_status(db=db, user=user, member=member, include_roles=True)


@router.delete("/bind", response_model=TaygedoStatusOut)
def taygedo_unbind(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    unbind_taygedo(db, member)
    return TaygedoStatusOut(bound=False)


@router.patch(
    "/bind",
    response_model=TaygedoStatusOut,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_update_bind(
    payload: TaygedoBindUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        update_bind_prefs(
            db,
            member,
            auto_checkin=payload.auto_checkin,
            checkin_hour=payload.checkin_hour,
            checkin_minute=payload.checkin_minute,
        )
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return taygedo_status(db=db, user=user, member=member, include_roles=False)


@router.post(
    "/checkin",
    response_model=TaygedoCheckinResponse,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_checkin_now(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        out = run_checkin_for_member(db, member, force=True)
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return build_checkin_response(
        out=out,
        response_cls=TaygedoCheckinResponse,
        result_cls=TaygedoCheckinResultItem,
    )
