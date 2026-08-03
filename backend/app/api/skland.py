"""森空岛：绑定状态、角色预览、手动/自动签到。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    ArknightsBoxOut,
    ArknightsCharOut,
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
from app.services.member_sync import ensure_user_member
from app.services.skland_checkin import (
    bind_skland,
    bind_skland_with_password,
    bind_skland_with_sms,
    get_arknights_box_for_member,
    get_bind_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    send_skland_sms,
    set_auto_checkin,
    unbind_skland,
)
from app.services.skland_client import SklandApiError
from app.services.skland_qr import poll_qr_bind, start_qr_bind

router = APIRouter(prefix="/skland", tags=["skland"])


def _member_or_404(db: Session, user: User) -> Member:
    member = ensure_user_member(db, user)
    if member is None:
        raise HTTPException(status_code=400, detail="用户尚未关联成员档案")
    return member


@router.get("/status", response_model=SklandStatusOut)
def skland_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_roles: bool = Query(default=True),
):
    member = _member_or_404(db, user)
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return SklandStatusOut(bound=False)

    roles: list[SklandRoleOut] = []
    today_results: list[SklandCheckinResultItem] = []
    token_ok: bool | None = None
    token_error: str | None = None
    summary = bind.last_checkin_summary

    try:
        live = query_today_for_bind(db, bind)
        today_results = [
            SklandCheckinResultItem(**r) for r in (live.get("results") or [])
        ]
        token_ok = True
        if live.get("summary"):
            summary = str(live["summary"])
    except SklandApiError as exc:
        token_ok = False
        token_error = exc.message

    if include_roles and token_ok is not False:
        try:
            roles = [
                SklandRoleOut(
                    game_code=r.game_code,
                    game_name=r.game_name,
                    uid=r.uid,
                    role_name=r.role_name,
                    channel_name=r.channel_name,
                )
                for r in preview_roles(db, member)
            ]
        except SklandApiError as exc:
            if token_ok is None:
                token_ok = False
                token_error = exc.message
            roles = []

    return SklandStatusOut(
        bound=True,
        auto_checkin=bool(bind.auto_checkin),
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


@router.get("/logs", response_model=list[SklandCheckinLogOut])
def skland_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    """已弃用：签到改为实时查询，不再返回历史记录。"""
    _ = (db, user, limit)
    return []


@router.get("/arknights/box", response_model=ArknightsBoxOut)
def skland_arknights_box(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    uid: str | None = Query(default=None, max_length=32),
):
    """明日方舟干员盒子（森空岛 player/info）。"""
    member = _member_or_404(db, user)
    try:
        box, role, roles = get_arknights_box_for_member(db, member, uid)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return ArknightsBoxOut(
        uid=box.uid,
        name=box.name,
        level=box.level,
        register_ts=box.register_ts,
        ap_current=box.ap_current,
        ap_max=box.ap_max,
        char_count=box.char_count,
        channel_name=role.channel_name,
        role_name=role.role_name,
        chars=[
            ArknightsCharOut(
                char_id=c.char_id,
                name=c.name,
                rarity=c.rarity,
                profession=c.profession,
                profession_label=c.profession_label,
                level=c.level,
                evolve_phase=c.evolve_phase,
                potential_rank=c.potential_rank,
                favor_percent=c.favor_percent,
                skin_id=c.skin_id,
                avatar_url=c.avatar_url,
                obtain_ts=c.obtain_ts,
            )
            for c in box.chars
        ],
        roles=[
            SklandRoleOut(
                game_code=r.game_code,
                game_name=r.game_name,
                uid=r.uid,
                role_name=r.role_name,
                channel_name=r.channel_name,
            )
            for r in roles
        ],
    )


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
    return skland_status(db=db, user=user, include_roles=True)


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
    return skland_status(db=db, user=user, include_roles=True)


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
    return skland_status(db=db, user=user, include_roles=True)


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
        status = skland_status(db=db, user=user, include_roles=True)
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


@router.patch("/bind", response_model=SklandStatusOut)
def skland_update_bind(
    payload: SklandBindUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        set_auto_checkin(db, member, payload.auto_checkin)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return skland_status(db=db, user=user, include_roles=False)


@router.post("/checkin", response_model=SklandCheckinResponse)
def skland_checkin_now(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = _member_or_404(db, user)
    try:
        out = run_checkin_for_member(db, member, force=True)
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return SklandCheckinResponse(
        skipped=bool(out.get("skipped")),
        ok=out.get("ok"),
        summary=str(out.get("summary") or ""),
        results=[SklandCheckinResultItem(**r) for r in out.get("results") or []],
    )
