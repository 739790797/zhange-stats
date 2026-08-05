"""森空岛：绑定状态、签到、绑定/解绑。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.platform_checkin import build_checkin_response, build_checkin_status
from app.api.skland.helpers import _member_or_404
from app.core.database import get_db
from app.core.deps import get_current_user, require_user_member
from app.core.platform_deps import require_feature
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    SklandBindPasswordRequest,
    SklandBindRequest,
    SklandBindSmsRequest,
    SklandBindSmsSendRequest,
    SklandBindSmsSendResponse,
    SklandBindUpdate,
    SklandCheckinLogOut,
    SklandCheckinResponse,
    SklandCheckinResultItem,
    SklandQrPollResponse,
    SklandQrStartResponse,
    SklandRoleOut,
    SklandStatusOut,
)
from app.services.skland_checkin import (
    bind_skland,
    bind_skland_with_password,
    bind_skland_with_sms,
    get_bind_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    send_skland_sms,
    unbind_skland,
)
from app.services.skland_client import SklandApiError
from app.services.skland_qr import poll_qr_bind, start_qr_bind

router = APIRouter(tags=["skland"])


@router.get("/status", response_model=SklandStatusOut)
def skland_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
    include_roles: bool = Query(default=True),
    force: bool = Query(default=False),
):
    _ = user
    bind = get_bind_for_member(db, member.id)

    def _ser_role(r: object) -> SklandRoleOut:
        return SklandRoleOut(
            game_code=r.game_code,  # type: ignore[attr-defined]
            game_name=r.game_name,  # type: ignore[attr-defined]
            uid=r.uid,  # type: ignore[attr-defined]
            role_name=r.role_name,  # type: ignore[attr-defined]
            channel_name=r.channel_name,  # type: ignore[attr-defined]
        )

    return build_checkin_status(
        db=db,
        member=member,
        bind=bind,
        status_cls=SklandStatusOut,
        role_cls=SklandRoleOut,
        result_cls=SklandCheckinResultItem,
        query_today=query_today_for_bind,
        preview_roles=preview_roles,
        api_error_cls=SklandApiError,
        include_roles=include_roles,
        force=force,
        serialize_role=_ser_role,
        soft_roles_on_none_ok=True,
    )


@router.get("/logs", response_model=list[SklandCheckinLogOut])
def skland_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    """已弃用：签到改为实时查询，不再返回历史记录。"""
    _ = (db, user, limit)
    return []


@router.post("/bind", response_model=SklandStatusOut)
def skland_bind(
    payload: SklandBindRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        bind_skland(db, member, payload.token)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return skland_status(db=db, user=user, member=_member_or_404(db, user), include_roles=True)


@router.post("/bind/password", response_model=SklandStatusOut)
def skland_bind_password(
    payload: SklandBindPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        bind_skland_with_password(db, member, payload.phone, payload.password)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return skland_status(db=db, user=user, member=_member_or_404(db, user), include_roles=True)


@router.post("/bind/sms/send", response_model=SklandBindSmsSendResponse)
def skland_bind_sms_send(
    payload: SklandBindSmsSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _member_or_404(db, user)
    try:
        send_skland_sms(payload.phone)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return SklandBindSmsSendResponse()


@router.post("/bind/sms", response_model=SklandStatusOut)
def skland_bind_sms(
    payload: SklandBindSmsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        bind_skland_with_sms(db, member, payload.phone, payload.code)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return skland_status(db=db, user=user, member=_member_or_404(db, user), include_roles=True)


@router.post("/qr/start", response_model=SklandQrStartResponse)
def skland_qr_start(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        out = start_qr_bind(user_id=user.id, member=member)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"生成二维码失败：{exc}") from exc
    return SklandQrStartResponse(**out)


@router.get("/qr/poll", response_model=SklandQrPollResponse)
def skland_qr_poll(
    scan_id: str = Query(min_length=4, max_length=128),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        out = poll_qr_bind(db, user_id=user.id, member=member, scan_id=scan_id)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    if out.get("status") == "ok":
        status = skland_status(db=db, user=user, member=member, include_roles=True)
        return SklandQrPollResponse(
            status="ok",
            message=str(out.get("message") or "扫码绑定成功"),
            bound=status.bound,
            auto_checkin=status.auto_checkin,
            roles=status.roles,
        )

    return SklandQrPollResponse(
        status=str(out.get("status") or "error"),
        message=str(out.get("message") or ""),
    )


@router.delete("/bind", response_model=SklandStatusOut)
def skland_unbind(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    unbind_skland(db, member)
    return SklandStatusOut(bound=False)


@router.patch(
    "/bind",
    response_model=SklandStatusOut,
    dependencies=[Depends(require_feature("skland.checkin"))],
)
def skland_update_bind(
    payload: SklandBindUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        from app.services.skland_checkin import update_bind_prefs

        update_bind_prefs(
            db,
            member,
            auto_checkin=payload.auto_checkin,
            checkin_hour=payload.checkin_hour,
            checkin_minute=payload.checkin_minute,
        )
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return skland_status(db=db, user=user, member=_member_or_404(db, user), include_roles=False)


@router.post(
    "/checkin",
    response_model=SklandCheckinResponse,
    dependencies=[Depends(require_feature("skland.checkin"))],
)
def skland_checkin_now(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        out = run_checkin_for_member(db, member, force=True)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return build_checkin_response(
        out=out,
        response_cls=SklandCheckinResponse,
        result_cls=SklandCheckinResultItem,
    )
