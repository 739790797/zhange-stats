"""塔吉多：绑定、异环签到状态与手动/自动签到。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.platform_checkin import (
    apply_role_membership_replace,
    apply_role_pref_update,
    build_checkin_response,
    build_checkin_status,
    build_role_membership_tree,
    raise_api_error,
    role_keys_from_now_body,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_user_member
from app.core.platform_deps import require_feature
from app.core.rate_limit import client_ip, platform_limiter
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    CheckinNowBody,
    CheckinRolePrefUpdate,
    ExastrisBoxOut,
    ExastrisCharOut,
    RoleMembershipReplaceBody,
    RoleMembershipTreeOut,
    TaygedoAttendanceCalendarOut,
    TaygedoAttendanceDayOut,
    TaygedoBindJsonRequest,
    TaygedoBindPasswordRequest,
    TaygedoBindSmsRequest,
    TaygedoBindSmsSendRequest,
    TaygedoBindSmsSendResponse,
    TaygedoBindUpdate,
    TaygedoCheckinLogOut,
    TaygedoCheckinResponse,
    TaygedoCheckinResultItem,
    TaygedoExchangeItemOut,
    TaygedoExchangeRequest,
    TaygedoExchangeResultOut,
    TaygedoExchangeRoleOut,
    TaygedoExchangeShopOut,
    TaygedoExchangeTabOut,
    TaygedoRoleOut,
    TaygedoStatusOut,
)
from app.schemas.checkin import CheckinAwardItem
from app.services.taygedo_boxes import get_exastris_box_for_member
from app.services.taygedo_checkin import (
    bind_with_credentials_json,
    bind_with_password,
    bind_with_sms,
    fetch_exchange_shop,
    get_bind_for_member,
    get_taygedo_attendance_calendar_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    run_exchange_for_member,
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
    force: bool = Query(
        default=True,
        description="展示路径默认回源官方；传 false 仅供内部/排障读今日 logs",
    ),
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
        role_pref_platform="taygedo",
    )


@router.get("/logs", response_model=list[TaygedoCheckinLogOut])
def taygedo_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    """兼容占位：历史列表已弃用；今日状态见 status（读 *_checkin_logs 缓存）。"""
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
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = (db, user, member)
    ip = client_ip(request)
    platform_limiter.hit(f"taygedo-sms:ip:{ip}", limit=10, window_sec=600)
    platform_limiter.hit(f"taygedo-sms:uid:{user.id}", limit=5, window_sec=600)
    platform_limiter.hit(
        f"taygedo-sms:phone:{payload.phone.strip()}", limit=5, window_sec=600
    )
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


@router.patch(
    "/role-prefs",
    response_model=TaygedoStatusOut,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_update_role_pref(
    payload: CheckinRolePrefUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise_api_error(TaygedoApiError("尚未绑定塔吉多"), TaygedoApiError)
    from app.services.checkin_role_prefs import PLATFORM_TAYGEDO

    apply_role_pref_update(
        db=db,
        platform=PLATFORM_TAYGEDO,
        member_id=member.id,
        bind=bind,
        payload=payload,
    )
    return taygedo_status(db=db, user=user, member=member, include_roles=False)


@router.get(
    "/role-tree",
    response_model=RoleMembershipTreeOut,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_role_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise_api_error(TaygedoApiError("尚未绑定塔吉多"), TaygedoApiError)
    from app.services.checkin_role_prefs import PLATFORM_TAYGEDO

    return build_role_membership_tree(
        db=db,
        platform=PLATFORM_TAYGEDO,
        member_id=member.id,
        preview_roles=preview_roles,
        member=member,
        api_error_cls=TaygedoApiError,
    )


@router.put(
    "/role-memberships",
    response_model=TaygedoStatusOut,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_replace_role_memberships(
    body: RoleMembershipReplaceBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise_api_error(TaygedoApiError("尚未绑定塔吉多"), TaygedoApiError)
    from app.services.checkin_role_prefs import PLATFORM_TAYGEDO

    apply_role_membership_replace(
        db=db,
        platform=PLATFORM_TAYGEDO,
        member_id=member.id,
        bind=bind,
        body=body,
    )
    return taygedo_status(db=db, user=user, member=member, include_roles=False)


@router.post(
    "/checkin",
    response_model=TaygedoCheckinResponse,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_checkin_now(
    body: CheckinNowBody | None = Body(default=None),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    role_keys = role_keys_from_now_body(body)
    try:
        out = run_checkin_for_member(
            db, member, force=True, role_keys=role_keys
        )
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return build_checkin_response(
        out=out,
        response_cls=TaygedoCheckinResponse,
        result_cls=TaygedoCheckinResultItem,
    )


@router.get(
    "/exchange",
    response_model=TaygedoExchangeShopOut,
    dependencies=[Depends(require_feature("taygedo.exchange"))],
)
def taygedo_exchange_shop(
    tab: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        data = fetch_exchange_shop(db, member, tab=tab)
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return TaygedoExchangeShopOut(
        gold=int(data.get("gold") or 0),
        today_get=int(data.get("today_get") or 0),
        today_total=int(data.get("today_total") or 0),
        tabs=[
            TaygedoExchangeTabOut(**t)
            for t in (data.get("tabs") or [])
            if isinstance(t, dict)
        ],
        items=[
            TaygedoExchangeItemOut(**item)
            for item in (data.get("items") or [])
            if isinstance(item, dict)
        ],
        roles=[
            TaygedoExchangeRoleOut(**r)
            for r in (data.get("roles") or [])
            if isinstance(r, dict)
        ],
    )


@router.post(
    "/exchange",
    response_model=TaygedoExchangeResultOut,
    dependencies=[Depends(require_feature("taygedo.exchange"))],
)
def taygedo_do_exchange(
    payload: TaygedoExchangeRequest,
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        out = run_exchange_for_member(
            db,
            member,
            goods_id=payload.goods_id,
            game_id=payload.game_id,
            role_id=payload.role_id,
        )
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    item = out.get("item")
    return TaygedoExchangeResultOut(
        ok=bool(out.get("ok")),
        message=str(out.get("message") or ""),
        gold=out.get("gold"),
        item=TaygedoExchangeItemOut(**item) if isinstance(item, dict) else None,
    )


@router.get(
    "/attendance-calendar",
    response_model=TaygedoAttendanceCalendarOut,
    dependencies=[Depends(require_feature("taygedo.checkin"))],
)
def taygedo_attendance_calendar(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
    game_code: str = Query(..., min_length=1, max_length=32),
    role_uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """异环 / 幻塔签到周期日历（第 N 天奖励，非公历）；默认读库，force 回源。"""
    try:
        parsed, role, roles, synced_at, stale = (
            get_taygedo_attendance_calendar_for_member(
                db,
                member,
                game_code=game_code,
                role_uid=role_uid,
                force=force,
            )
        )
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)

    days = [
        TaygedoAttendanceDayOut(
            day=int(d["day"]),
            claimed=bool(d["claimed"]),
            awards=[CheckinAwardItem(**a) for a in (d.get("awards") or [])],
        )
        for d in (parsed.get("days") or [])
        if isinstance(d, dict)
    ]
    return TaygedoAttendanceCalendarOut(
        game_code=role.game_code,
        game_name=role.game_name,
        uid=role.role_id,
        role_name=role.role_name,
        claimed_days=int(parsed.get("claimed_days") or 0),
        total_days=int(parsed.get("total_days") or 0),
        has_today_claim=bool(parsed.get("has_today_claim")),
        progress_reliable=bool(parsed.get("progress_reliable", True)),
        days=days,
        roles=[
            TaygedoRoleOut(
                game_code=r.game_code,
                game_name=r.game_name,
                uid=r.role_id,
                role_name=r.role_name,
                channel_name=r.game_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


def _exastris_box_out(box, _role, roles, synced_at, stale: bool) -> ExastrisBoxOut:
    return ExastrisBoxOut(
        uid=box.uid,
        role_id=box.role_id,
        role_name=box.role_name,
        game_code=box.game_code,
        game_name=box.game_name,
        char_count=box.char_count,
        chars=[
            ExastrisCharOut(
                char_id=c.char_id,
                name=c.name,
                quality=c.quality,
                element_type=c.element_type,
                group_type=c.group_type,
                awaken_lev=c.awaken_lev,
                portrait_url=c.portrait_url,
                element_icon_url=c.element_icon_url,
            )
            for c in box.chars
        ],
        roles=[
            TaygedoRoleOut(
                game_code=r.game_code,
                game_name=r.game_name,
                uid=r.role_id,
                role_name=r.role_name,
                channel_name=r.game_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


@router.get(
    "/exastris/box",
    response_model=ExastrisBoxOut,
    dependencies=[Depends(require_feature("taygedo.exastris"))],
)
def taygedo_exastris_box(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
    uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """异环角色盒子：默认读库二次加工；force 或首次回源落库。"""
    try:
        box, role, roles, synced_at, stale = get_exastris_box_for_member(
            db, member, uid, force=force
        )
    except TaygedoApiError as exc:
        raise_api_error(exc, TaygedoApiError)
    return _exastris_box_out(box, role, roles, synced_at, stale)
