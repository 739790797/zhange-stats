"""库街区：绑定、社区/游戏签到状态与手动签到。"""

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
    KujiequBindSmsRequest,
    KujiequBindSmsSendRequest,
    KujiequBindSmsSendResponse,
    KujiequBindTokenRequest,
    KujiequBindUpdate,
    KujiequCheckinLogOut,
    KujiequCheckinResponse,
    KujiequCheckinResultItem,
    KujiequRoleOut,
    KujiequStatusOut,
)
from app.services.kujiequ_checkin import (
    bind_with_sms,
    bind_with_token,
    get_bind_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    unbind_kujiequ,
    update_bind_prefs,
)
from app.services.kujiequ_client import KujiequApiError, send_sms_captcha

router = APIRouter(
    prefix="/kujiequ",
    tags=["kujiequ"],
    dependencies=[Depends(require_feature("kujiequ"))],
)


@router.get("/status", response_model=KujiequStatusOut)
def kujiequ_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
    include_roles: bool = Query(default=True),
    force: bool = Query(default=False),
):
    _ = user
    bind = get_bind_for_member(db, member.id)
    return build_checkin_status(
        db=db,
        member=member,
        bind=bind,
        status_cls=KujiequStatusOut,
        role_cls=KujiequRoleOut,
        result_cls=KujiequCheckinResultItem,
        query_today=query_today_for_bind,
        preview_roles=preview_roles,
        api_error_cls=KujiequApiError,
        include_roles=include_roles,
        force=force,
        extra_fields={"phone_mask": bind.phone_mask if bind else None},
    )


@router.get("/logs", response_model=list[KujiequCheckinLogOut])
def kujiequ_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    _ = (db, user, limit)
    return []


@router.post("/bind/token", response_model=KujiequStatusOut)
def kujiequ_bind_token(
    payload: KujiequBindTokenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_token(db, member, payload.token)
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return kujiequ_status(db=db, user=user, member=member, include_roles=True)


@router.post("/bind/sms/send", response_model=KujiequBindSmsSendResponse)
def kujiequ_bind_sms_send(
    payload: KujiequBindSmsSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = (db, user, member)
    try:
        result = send_sms_captcha(payload.phone, payload.gee_test_data)
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return KujiequBindSmsSendResponse(
        ok=result.ok,
        message=result.message,
        need_geetest=result.need_geetest,
        captcha_id=result.captcha_id if result.need_geetest else None,
    )


@router.post("/bind/sms", response_model=KujiequStatusOut)
def kujiequ_bind_sms(
    payload: KujiequBindSmsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_sms(db, member, payload.phone, payload.captcha)
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return kujiequ_status(db=db, user=user, member=member, include_roles=True)


@router.delete("/bind", response_model=KujiequStatusOut)
def kujiequ_unbind(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    unbind_kujiequ(db, member)
    return KujiequStatusOut(bound=False)


@router.patch(
    "/bind",
    response_model=KujiequStatusOut,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_patch_bind(
    payload: KujiequBindUpdate,
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
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return kujiequ_status(db=db, user=user, member=member, include_roles=True)


@router.post(
    "/checkin",
    response_model=KujiequCheckinResponse,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_checkin(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        result = run_checkin_for_member(db, member, force=True)
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return build_checkin_response(
        out=result,
        response_cls=KujiequCheckinResponse,
        result_cls=KujiequCheckinResultItem,
    )
