"""库街区：绑定、社区/游戏签到状态与手动签到。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
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
from app.services.member_sync import ensure_user_member

router = APIRouter(
    prefix="/kujiequ",
    tags=["kujiequ"],
    dependencies=[Depends(require_feature("kujiequ"))],
)


def _member_or_404(db: Session, user: User) -> Member:
    member = ensure_user_member(db, user)
    if member is None:
        raise HTTPException(status_code=400, detail="用户尚未关联成员档案")
    return member


@router.get("/status", response_model=KujiequStatusOut)
def kujiequ_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_roles: bool = Query(default=True),
    force: bool = Query(default=False),
):
    member = _member_or_404(db, user)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return KujiequStatusOut(bound=False)

    roles: list[KujiequRoleOut] = []
    today_results: list[KujiequCheckinResultItem] = []
    token_ok: bool | None = None
    token_error: str | None = None
    summary = bind.last_checkin_summary

    try:
        live = query_today_for_bind(db, bind, force=force)
        today_results = [
            KujiequCheckinResultItem(**r) for r in (live.get("results") or [])
        ]
        token_ok = True
        if live.get("summary"):
            summary = str(live["summary"])
    except KujiequApiError as exc:
        token_ok = False
        token_error = exc.message

    if include_roles and token_ok is not False:
        try:
            roles = [KujiequRoleOut(**r) for r in preview_roles(db, member)]
        except KujiequApiError as exc:
            token_ok = False
            token_error = token_error or exc.message
            roles = []

    return KujiequStatusOut(
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
):
    member = _member_or_404(db, user)
    try:
        bind_with_token(db, member, payload.token)
    except KujiequApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return kujiequ_status(db=db, user=user, include_roles=True)


@router.post("/bind/sms/send", response_model=KujiequBindSmsSendResponse)
def kujiequ_bind_sms_send(
    payload: KujiequBindSmsSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _member_or_404(db, user)
    try:
        result = send_sms_captcha(payload.phone, payload.gee_test_data)
    except KujiequApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
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
):
    member = _member_or_404(db, user)
    try:
        bind_with_sms(db, member, payload.phone, payload.captcha)
    except KujiequApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return kujiequ_status(db=db, user=user, include_roles=True)


@router.delete("/bind", response_model=KujiequStatusOut)
def kujiequ_unbind(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
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
    except KujiequApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return kujiequ_status(db=db, user=user, include_roles=True)


@router.post(
    "/checkin",
    response_model=KujiequCheckinResponse,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_checkin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        result = run_checkin_for_member(db, member, force=True)
    except KujiequApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return KujiequCheckinResponse(
        skipped=bool(result.get("skipped")),
        ok=result.get("ok"),
        summary=str(result.get("summary") or ""),
        results=[KujiequCheckinResultItem(**r) for r in (result.get("results") or [])],
    )
