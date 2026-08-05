"""塔吉多：绑定、异环签到状态与手动/自动签到。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
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
from app.services.member_sync import ensure_user_member
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


def _member_or_404(db: Session, user: User) -> Member:
    member = ensure_user_member(db, user)
    if member is None:
        raise HTTPException(status_code=400, detail="用户尚未关联成员档案")
    return member


@router.get("/status", response_model=TaygedoStatusOut)
def taygedo_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_roles: bool = Query(default=True),
    force: bool = Query(default=False),
):
    member = _member_or_404(db, user)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return TaygedoStatusOut(bound=False)

    roles: list[TaygedoRoleOut] = []
    today_results: list[TaygedoCheckinResultItem] = []
    token_ok: bool | None = None
    token_error: str | None = None
    summary = bind.last_checkin_summary

    try:
        live = query_today_for_bind(db, bind, force=force)
        today_results = [
            TaygedoCheckinResultItem(**r) for r in (live.get("results") or [])
        ]
        token_ok = True
        if live.get("summary"):
            summary = str(live["summary"])
    except TaygedoApiError as exc:
        token_ok = False
        token_error = exc.message

    if include_roles and token_ok is not False:
        try:
            roles = [TaygedoRoleOut(**r) for r in preview_roles(db, member)]
        except TaygedoApiError as exc:
            token_ok = False
            token_error = token_error or exc.message
            roles = []

    return TaygedoStatusOut(
        bound=True,
        auto_checkin=bool(bind.auto_checkin),
        checkin_hour=int(bind.checkin_hour),
        checkin_minute=int(bind.checkin_minute),
        phone_mask=bind.phone_mask,
        bound_at=bind.bound_at,
        last_checkin_at=bind.last_checkin_at,
        last_checkin_date=bind.last_checkin_date.isoformat()
        if bind.last_checkin_date
        else None,
        last_checkin_ok=bind.last_checkin_ok,
        last_checkin_summary=summary,
        token_ok=token_ok,
        token_error=token_error,
        roles=roles,
        today_results=today_results,
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
):
    member = _member_or_404(db, user)
    try:
        bind_with_password(db, member, payload.phone, payload.password)
    except TaygedoApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return taygedo_status(db=db, user=user, include_roles=True)


@router.post("/bind/sms/send", response_model=TaygedoBindSmsSendResponse)
def taygedo_bind_sms_send(
    payload: TaygedoBindSmsSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _member_or_404(db, user)
    try:
        device_id = send_sms_captcha(payload.phone, payload.device_id)
    except TaygedoApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return TaygedoBindSmsSendResponse(device_id=device_id, message="验证码已发送")


@router.post("/bind/sms", response_model=TaygedoStatusOut)
def taygedo_bind_sms(
    payload: TaygedoBindSmsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        bind_with_sms(db, member, payload.phone, payload.captcha, payload.device_id)
    except TaygedoApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return taygedo_status(db=db, user=user, include_roles=True)


@router.post("/bind/json", response_model=TaygedoStatusOut)
def taygedo_bind_json(
    payload: TaygedoBindJsonRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        bind_with_credentials_json(db, member, payload.credentials_json)
    except TaygedoApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return taygedo_status(db=db, user=user, include_roles=True)


@router.delete("/bind", response_model=TaygedoStatusOut)
def taygedo_unbind(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
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
):
    member = _member_or_404(db, user)
    try:
        update_bind_prefs(
            db,
            member,
            auto_checkin=payload.auto_checkin,
            checkin_hour=payload.checkin_hour,
            checkin_minute=payload.checkin_minute,
        )
    except TaygedoApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return taygedo_status(db=db, user=user, include_roles=False)


@router.post(
    "/checkin",
    response_model=TaygedoCheckinResponse,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_checkin_now(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        out = run_checkin_for_member(db, member, force=True)
    except TaygedoApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return TaygedoCheckinResponse(
        skipped=bool(out.get("skipped")),
        ok=out.get("ok"),
        summary=str(out.get("summary") or ""),
        results=[TaygedoCheckinResultItem(**r) for r in out.get("results") or []],
    )
