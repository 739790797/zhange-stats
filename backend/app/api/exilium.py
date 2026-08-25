"""追放社区：绑定状态与手动/自动签到。"""

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
    ExiliumBindPasswordRequest,
    ExiliumBindSmsRequest,
    ExiliumBindSmsSendRequest,
    ExiliumBindSmsSendResponse,
    ExiliumBindUpdate,
    ExiliumCheckinResponse,
    ExiliumCheckinResultItem,
    ExiliumExchangeItemOut,
    ExiliumExchangeRequest,
    ExiliumExchangeResultOut,
    ExiliumExchangeShopOut,
    ExiliumRoleOut,
    ExiliumScoreLogItemOut,
    ExiliumScoreLogOut,
    ExiliumStatusOut,
    RoleMembershipReplaceBody,
    RoleMembershipTreeOut,
)
from app.services.exilium.checkin import (
    bind_with_password,
    bind_with_sms,
    fetch_exchange_shop,
    fetch_score_logs,
    get_bind_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    run_exchange_for_member,
    unbind_exilium,
    update_bind_prefs,
)
from app.services.exilium.client import (
    ExiliumApiError,
    ExiliumNeedGraphCaptcha,
    send_sms,
)

router = APIRouter(
    prefix="/exilium",
    tags=["exilium"],
    dependencies=[Depends(require_feature("exilium"))],
)


@router.get("/status", response_model=ExiliumStatusOut)
def exilium_status(
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
        status_cls=ExiliumStatusOut,
        role_cls=ExiliumRoleOut,
        result_cls=ExiliumCheckinResultItem,
        query_today=query_today_for_bind,
        preview_roles=preview_roles,
        api_error_cls=ExiliumApiError,
        include_roles=include_roles,
        force=force,
        extra_fields={"phone_mask": bind.phone_mask if bind else None},
        role_pref_platform="exilium",
    )


@router.get("/logs")
def exilium_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    """兼容占位：历史列表已弃用；今日状态见 status（读 *_checkin_logs 缓存）。"""
    _ = (db, user, limit)
    return []


@router.post("/bind/password", response_model=ExiliumStatusOut)
def exilium_bind_password(
    payload: ExiliumBindPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_password(db, member, payload.account, payload.password)
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return exilium_status(db=db, user=user, member=member, include_roles=True)


@router.post("/bind/sms/send", response_model=ExiliumBindSmsSendResponse)
def exilium_bind_sms_send(
    payload: ExiliumBindSmsSendRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = (db, user, member)
    ip = client_ip(request)
    platform_limiter.hit(f"exilium-sms:ip:{ip}", limit=10, window_sec=600)
    platform_limiter.hit(f"exilium-sms:uid:{user.id}", limit=5, window_sec=600)
    platform_limiter.hit(
        f"exilium-sms:phone:{payload.phone.strip()}", limit=5, window_sec=600
    )
    try:
        send_sms(payload.phone, payload.graph_code)
    except ExiliumNeedGraphCaptcha as exc:
        return ExiliumBindSmsSendResponse(
            ok=False,
            need_graph_captcha=True,
            graph_captcha_image=exc.image,
            message="请输入图形验证码后重新发送",
        )
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return ExiliumBindSmsSendResponse(ok=True, message="验证码已发送")


@router.post("/bind/sms", response_model=ExiliumStatusOut)
def exilium_bind_sms(
    payload: ExiliumBindSmsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    try:
        bind_with_sms(db, member, payload.phone, payload.captcha)
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return exilium_status(db=db, user=user, member=member, include_roles=True)


@router.delete("/bind", response_model=ExiliumStatusOut)
def exilium_unbind(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    unbind_exilium(db, member)
    return ExiliumStatusOut(bound=False)


@router.patch(
    "/bind",
    response_model=ExiliumStatusOut,
    dependencies=[Depends(require_feature("exilium.checkin"))],
)
def exilium_update_bind(
    payload: ExiliumBindUpdate,
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
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return exilium_status(db=db, user=user, member=member, include_roles=False)


@router.patch(
    "/role-prefs",
    response_model=ExiliumStatusOut,
    dependencies=[Depends(require_feature("exilium.checkin"))],
)
def exilium_update_role_pref(
    payload: CheckinRolePrefUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定追放社区")
    from app.services.checkin.role_prefs import PLATFORM_EXILIUM

    apply_role_pref_update(
        db=db,
        platform=PLATFORM_EXILIUM,
        member_id=member.id,
        bind=bind,
        payload=payload,
    )
    return exilium_status(db=db, user=user, member=member, include_roles=False)


@router.get(
    "/role-tree",
    response_model=RoleMembershipTreeOut,
    dependencies=[Depends(require_feature("exilium.checkin"))],
)
def exilium_role_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定追放社区")
    from app.services.checkin.role_prefs import PLATFORM_EXILIUM
    from app.services.exilium.client import ExiliumApiError

    return build_role_membership_tree(
        db=db,
        platform=PLATFORM_EXILIUM,
        member_id=member.id,
        preview_roles=preview_roles,
        member=member,
        api_error_cls=ExiliumApiError,
    )


@router.put(
    "/role-memberships",
    response_model=ExiliumStatusOut,
    dependencies=[Depends(require_feature("exilium.checkin"))],
)
def exilium_replace_role_memberships(
    body: RoleMembershipReplaceBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定追放社区")
    from app.services.checkin.role_prefs import PLATFORM_EXILIUM

    apply_role_membership_replace(
        db=db,
        platform=PLATFORM_EXILIUM,
        member_id=member.id,
        bind=bind,
        body=body,
    )
    return exilium_status(db=db, user=user, member=member, include_roles=False)


@router.post(
    "/checkin",
    response_model=ExiliumCheckinResponse,
    dependencies=[Depends(require_feature("exilium.checkin"))],
)
def exilium_checkin_now(
    body: CheckinNowBody | None = Body(default=None),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    role_keys = role_keys_from_now_body(body)
    try:
        out = run_checkin_for_member(
            db, member, force=True, role_keys=role_keys
        )
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return build_checkin_response(
        out=out,
        response_cls=ExiliumCheckinResponse,
        result_cls=ExiliumCheckinResultItem,
    )


@router.get(
    "/exchange",
    response_model=ExiliumExchangeShopOut,
    dependencies=[Depends(require_feature("exilium.exchange"))],
)
def exilium_exchange_shop(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        data = fetch_exchange_shop(db, member)
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return ExiliumExchangeShopOut(
        score=int(data.get("score") or 0),
        items=[ExiliumExchangeItemOut(**item) for item in data.get("items") or []],
    )


@router.post(
    "/exchange",
    response_model=ExiliumExchangeResultOut,
    dependencies=[Depends(require_feature("exilium.exchange"))],
)
def exilium_do_exchange(
    payload: ExiliumExchangeRequest,
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        out = run_exchange_for_member(db, member, payload.exchange_id)
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    item = out.get("item")
    return ExiliumExchangeResultOut(
        ok=bool(out.get("ok")),
        message=str(out.get("message") or ""),
        score=out.get("score"),
        item=ExiliumExchangeItemOut(**item) if isinstance(item, dict) else None,
    )


@router.get(
    "/score-logs",
    response_model=ExiliumScoreLogOut,
    dependencies=[Depends(require_feature("exilium.exchange"))],
)
def exilium_score_logs(
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    """积分变动记录（对应官方 points_Log）。"""
    try:
        data = fetch_score_logs(db, member, page=page, page_size=page_size)
    except ExiliumApiError as exc:
        raise_api_error(exc, ExiliumApiError)
    return ExiliumScoreLogOut(
        items=[ExiliumScoreLogItemOut(**row) for row in data.get("list") or []],
        total=int(data.get("total") or 0),
        page=int(data.get("page") or page),
        page_size=int(data.get("page_size") or page_size),
    )
