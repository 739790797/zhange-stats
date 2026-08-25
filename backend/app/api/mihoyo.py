"""米游社：绑定状态与手动/自动签到。"""

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
from app.schemas.checkin import CheckinAwardItem
from app.schemas import (
    CheckinNowBody,
    CheckinRolePrefUpdate,
    MihoyoAttendanceCalendarOut,
    MihoyoAttendanceDayOut,
    MihoyoBindPasswordRequest,
    MihoyoBindPasswordResponse,
    MihoyoBindSmsRequest,
    MihoyoBindSmsSendRequest,
    MihoyoBindSmsSendResponse,
    MihoyoBindUpdate,
    MihoyoCheckinResponse,
    MihoyoCheckinResultItem,
    MihoyoExchangeItemOut,
    MihoyoExchangeRequest,
    MihoyoExchangeResultOut,
    MihoyoExchangeRoleOut,
    MihoyoExchangeShopOut,
    MihoyoPointsLogItemOut,
    MihoyoPointsLogOut,
    MihoyoQrPollRequest,
    MihoyoQrPollResponse,
    MihoyoQrStartResponse,
    MihoyoRoleOut,
    MihoyoStatusOut,
    RoleMembershipReplaceBody,
    RoleMembershipTreeOut,
)
from app.services.mihoyo_auth import MihoyoNeedGeetest
from app.services.mihoyo_checkin import (
    bind_member_with_password,
    bind_member_with_sms,
    fetch_exchange_shop,
    fetch_points_logs,
    get_bind_for_member,
    get_mihoyo_attendance_calendar_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    run_exchange_for_member,
    send_sms_for_bind,
    unbind_mihoyo,
    update_bind_prefs,
)
from app.services.mihoyo_client import MihoyoApiError
from app.services.mihoyo_qr import poll_qr_bind, start_qr_bind

router = APIRouter(
    prefix="/mihoyo",
    tags=["mihoyo"],
    dependencies=[Depends(require_feature("mihoyo"))],
)


@router.get("/status", response_model=MihoyoStatusOut)
def mihoyo_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
    include_roles: bool = Query(default=True),
    force: bool = Query(
        default=True,
        description="展示路径默认回源官方；传 false 仅供内部/排障读今日 logs",
    ),
):
    _ = user
    bind = get_bind_for_member(db, member.id)
    return build_checkin_status(
        db=db,
        member=member,
        bind=bind,
        status_cls=MihoyoStatusOut,
        role_cls=MihoyoRoleOut,
        result_cls=MihoyoCheckinResultItem,
        query_today=query_today_for_bind,
        preview_roles=preview_roles,
        api_error_cls=MihoyoApiError,
        include_roles=include_roles,
        force=force,
        extra_fields={"phone_mask": bind.phone_mask if bind else None},
        role_pref_platform="mihoyo",
    )


@router.get("/logs")
def mihoyo_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    _ = (db, user, limit)
    return []


@router.post("/bind/sms/send", response_model=MihoyoBindSmsSendResponse)
def mihoyo_bind_sms_send(
    payload: MihoyoBindSmsSendRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = (db, member)
    ip = client_ip(request)
    platform_limiter.hit(f"mihoyo-sms:ip:{ip}", limit=10, window_sec=600)
    platform_limiter.hit(f"mihoyo-sms:uid:{user.id}", limit=5, window_sec=600)
    platform_limiter.hit(
        f"mihoyo-sms:phone:{payload.phone.strip()}", limit=5, window_sec=600
    )
    try:
        out = send_sms_for_bind(
            payload.phone,
            geetest=payload.geetest,
            mmt_key=payload.mmt_key,
        )
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return MihoyoBindSmsSendResponse(
        ok=bool(out.get("ok", True)),
        message=str(out.get("message") or "验证码已发送"),
        need_geetest=bool(out.get("need_geetest")),
        captcha_id=out.get("captcha_id"),
        mmt_key=out.get("mmt_key"),
    )


@router.post("/bind/sms", response_model=MihoyoStatusOut)
def mihoyo_bind_sms(
    payload: MihoyoBindSmsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_member_with_sms(db, member, payload.phone, payload.captcha)
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return mihoyo_status(db=db, user=user, member=member, include_roles=True)


@router.post("/bind/password", response_model=MihoyoBindPasswordResponse)
def mihoyo_bind_password(
    payload: MihoyoBindPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_member_with_password(
            db,
            member,
            payload.account,
            payload.password,
            geetest=payload.geetest,
            mmt_key=payload.mmt_key,
        )
    except MihoyoNeedGeetest as exc:
        return MihoyoBindPasswordResponse(
            ok=False,
            need_geetest=True,
            captcha_id=exc.captcha_id,
            mmt_key=exc.mmt_key,
            message=exc.message,
        )
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    status = mihoyo_status(db=db, user=user, member=member, include_roles=True)
    return MihoyoBindPasswordResponse(ok=True, message="绑定成功", status=status)


@router.post("/qr/start", response_model=MihoyoQrStartResponse)
def mihoyo_qr_start(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = db
    try:
        out = start_qr_bind(user_id=user.id, member=member)
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return MihoyoQrStartResponse(**out)


@router.post("/qr/poll", response_model=MihoyoQrPollResponse)
def mihoyo_qr_poll(
    payload: MihoyoQrPollRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        out = poll_qr_bind(
            db, user_id=user.id, member=member, scan_id=payload.scan_id
        )
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return MihoyoQrPollResponse(
        status=str(out.get("status") or "error"),
        message=str(out.get("message") or ""),
    )


@router.delete("/bind", response_model=MihoyoStatusOut)
def mihoyo_unbind(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    unbind_mihoyo(db, member)
    return MihoyoStatusOut(bound=False)


@router.patch(
    "/bind",
    response_model=MihoyoStatusOut,
    dependencies=[Depends(require_feature("mihoyo.checkin"))],
)
def mihoyo_update_bind(
    payload: MihoyoBindUpdate,
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
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return mihoyo_status(db=db, user=user, member=member, include_roles=False)


@router.patch(
    "/role-prefs",
    response_model=MihoyoStatusOut,
    dependencies=[Depends(require_feature("mihoyo.checkin"))],
)
def mihoyo_update_role_pref(
    payload: CheckinRolePrefUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定米游社")
    from app.services.checkin_role_prefs import PLATFORM_MIHOYO

    apply_role_pref_update(
        db=db,
        platform=PLATFORM_MIHOYO,
        member_id=member.id,
        bind=bind,
        payload=payload,
    )
    return mihoyo_status(db=db, user=user, member=member, include_roles=False)


@router.get(
    "/role-tree",
    response_model=RoleMembershipTreeOut,
    dependencies=[Depends(require_feature("mihoyo.checkin"))],
)
def mihoyo_role_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定米游社")
    from app.services.checkin_role_prefs import PLATFORM_MIHOYO

    return build_role_membership_tree(
        db=db,
        platform=PLATFORM_MIHOYO,
        member_id=member.id,
        preview_roles=preview_roles,
        member=member,
        api_error_cls=MihoyoApiError,
    )


@router.put(
    "/role-memberships",
    response_model=MihoyoStatusOut,
    dependencies=[Depends(require_feature("mihoyo.checkin"))],
)
def mihoyo_replace_role_memberships(
    body: RoleMembershipReplaceBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定米游社")
    from app.services.checkin_role_prefs import PLATFORM_MIHOYO

    apply_role_membership_replace(
        db=db,
        platform=PLATFORM_MIHOYO,
        member_id=member.id,
        bind=bind,
        body=body,
    )
    return mihoyo_status(db=db, user=user, member=member, include_roles=False)


@router.post(
    "/checkin",
    response_model=MihoyoCheckinResponse,
    dependencies=[Depends(require_feature("mihoyo.checkin"))],
)
def mihoyo_checkin_now(
    body: CheckinNowBody | None = Body(default=None),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    role_keys = role_keys_from_now_body(body)
    try:
        out = run_checkin_for_member(
            db, member, force=True, role_keys=role_keys
        )
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return build_checkin_response(
        out=out,
        response_cls=MihoyoCheckinResponse,
        result_cls=MihoyoCheckinResultItem,
    )


@router.get(
    "/exchange",
    response_model=MihoyoExchangeShopOut,
    dependencies=[Depends(require_feature("mihoyo.exchange"))],
)
def mihoyo_exchange_shop(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        data = fetch_exchange_shop(db, member)
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return MihoyoExchangeShopOut(
        points=int(data.get("points") or 0),
        items=[MihoyoExchangeItemOut(**item) for item in data.get("items") or []],
        roles=[MihoyoExchangeRoleOut(**role) for role in data.get("roles") or []],
    )


@router.post(
    "/exchange",
    response_model=MihoyoExchangeResultOut,
    dependencies=[Depends(require_feature("mihoyo.exchange"))],
)
def mihoyo_do_exchange(
    payload: MihoyoExchangeRequest,
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        out = run_exchange_for_member(
            db,
            member,
            goods_id=payload.goods_id,
            game_biz=payload.game_biz,
            region=payload.region,
            role_uid=payload.role_uid,
        )
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    item = out.get("item")
    return MihoyoExchangeResultOut(
        ok=bool(out.get("ok")),
        message=str(out.get("message") or ""),
        points=out.get("points"),
        item=MihoyoExchangeItemOut(**item) if isinstance(item, dict) else None,
    )


@router.get(
    "/points-logs",
    response_model=MihoyoPointsLogOut,
    dependencies=[Depends(require_feature("mihoyo.exchange"))],
)
def mihoyo_points_logs(
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        data = fetch_points_logs(db, member, page=page, page_size=page_size)
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)
    return MihoyoPointsLogOut(
        items=[MihoyoPointsLogItemOut(**row) for row in data.get("list") or []],
        total=int(data.get("total") or 0),
        page=int(data.get("page") or page),
        page_size=int(data.get("page_size") or page_size),
    )


@router.get(
    "/attendance-calendar",
    response_model=MihoyoAttendanceCalendarOut,
    dependencies=[Depends(require_feature("mihoyo.checkin"))],
)
def mihoyo_attendance_calendar(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
    game_code: str = Query(..., min_length=1, max_length=32),
    role_uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """游戏福利签到周期日历（第 N 天奖励，非公历）；默认读库，force 回源。"""
    try:
        parsed, role, roles, synced_at, stale = (
            get_mihoyo_attendance_calendar_for_member(
                db,
                member,
                game_code=game_code,
                role_uid=role_uid,
                force=force,
            )
        )
    except MihoyoApiError as exc:
        raise_api_error(exc, MihoyoApiError)

    days = [
        MihoyoAttendanceDayOut(
            day=int(d["day"]),
            claimed=bool(d["claimed"]),
            awards=[CheckinAwardItem(**a) for a in (d.get("awards") or [])],
        )
        for d in (parsed.get("days") or [])
        if isinstance(d, dict)
    ]
    return MihoyoAttendanceCalendarOut(
        game_code=role.game_code,
        game_name=role.game_name,
        uid=role.role_uid,
        role_name=role.role_name,
        claimed_days=int(parsed.get("claimed_days") or 0),
        total_days=int(parsed.get("total_days") or 0),
        has_today_claim=bool(parsed.get("has_today_claim")),
        progress_reliable=bool(parsed.get("progress_reliable", True)),
        days=days,
        roles=[
            MihoyoRoleOut(
                game_code=r.game_code,
                game_name=r.game_name,
                uid=r.role_uid,
                role_name=r.role_name,
                channel_name=r.channel_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )
