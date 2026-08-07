"""库街区：绑定、社区/游戏签到状态与手动签到。"""

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
    KujiequAttendanceCalendarOut,
    KujiequAttendanceDayOut,
    KujiequBindSmsRequest,
    KujiequBindSmsSendRequest,
    KujiequBindSmsSendResponse,
    KujiequBindTokenRequest,
    KujiequBindUpdate,
    KujiequCheckinLogOut,
    KujiequCheckinResponse,
    KujiequCheckinResultItem,
    KujiequExchangeItemOut,
    KujiequExchangeRequest,
    KujiequExchangeResultOut,
    KujiequExchangeRoleOut,
    KujiequExchangeShopOut,
    KujiequRoleOut,
    KujiequStatusOut,
    RoleMembershipReplaceBody,
    RoleMembershipTreeOut,
    WwBoxItemOut,
    WwBoxOut,
)
from app.schemas.checkin import CheckinAwardItem
from app.services.kujiequ_boxes import get_ww_box_for_member
from app.services.kujiequ_checkin import (
    bind_with_sms,
    bind_with_token,
    fetch_exchange_shop,
    get_bind_for_member,
    get_kujiequ_attendance_calendar_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    run_exchange_for_member,
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
        status_cls=KujiequStatusOut,
        role_cls=KujiequRoleOut,
        result_cls=KujiequCheckinResultItem,
        query_today=query_today_for_bind,
        preview_roles=preview_roles,
        api_error_cls=KujiequApiError,
        include_roles=include_roles,
        force=force,
        extra_fields={"phone_mask": bind.phone_mask if bind else None},
        role_pref_platform="kujiequ",
    )


@router.get("/logs", response_model=list[KujiequCheckinLogOut])
def kujiequ_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
):
    """兼容占位：历史列表已弃用；今日状态见 status（读 *_checkin_logs 缓存）。"""
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
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    _ = (db, user, member)
    ip = client_ip(request)
    platform_limiter.hit(f"kujiequ-sms:ip:{ip}", limit=10, window_sec=600)
    platform_limiter.hit(f"kujiequ-sms:uid:{user.id}", limit=5, window_sec=600)
    platform_limiter.hit(
        f"kujiequ-sms:phone:{payload.phone.strip()}", limit=5, window_sec=600
    )
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


@router.patch(
    "/role-prefs",
    response_model=KujiequStatusOut,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_update_role_pref(
    payload: CheckinRolePrefUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定库街区")
    from app.services.checkin_role_prefs import PLATFORM_KUJIEQU

    apply_role_pref_update(
        db=db,
        platform=PLATFORM_KUJIEQU,
        member_id=member.id,
        bind=bind,
        payload=payload,
    )
    return kujiequ_status(db=db, user=user, member=member, include_roles=False)


@router.get(
    "/role-tree",
    response_model=RoleMembershipTreeOut,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_role_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定库街区")
    from app.services.checkin_role_prefs import PLATFORM_KUJIEQU

    return build_role_membership_tree(
        db=db,
        platform=PLATFORM_KUJIEQU,
        member_id=member.id,
        preview_roles=preview_roles,
        member=member,
        api_error_cls=KujiequApiError,
    )


@router.put(
    "/role-memberships",
    response_model=KujiequStatusOut,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_replace_role_memberships(
    body: RoleMembershipReplaceBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    member: Member = Depends(require_user_member),
):
    from fastapi import HTTPException

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        raise HTTPException(status_code=400, detail="尚未绑定库街区")
    from app.services.checkin_role_prefs import PLATFORM_KUJIEQU

    apply_role_membership_replace(
        db=db,
        platform=PLATFORM_KUJIEQU,
        member_id=member.id,
        bind=bind,
        body=body,
    )
    return kujiequ_status(db=db, user=user, member=member, include_roles=False)


@router.post(
    "/checkin",
    response_model=KujiequCheckinResponse,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_checkin(
    body: CheckinNowBody | None = Body(default=None),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    role_keys = role_keys_from_now_body(body)
    try:
        result = run_checkin_for_member(
            db, member, force=True, role_keys=role_keys
        )
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return build_checkin_response(
        out=result,
        response_cls=KujiequCheckinResponse,
        result_cls=KujiequCheckinResultItem,
    )


@router.get(
    "/exchange",
    response_model=KujiequExchangeShopOut,
    dependencies=[Depends(require_feature("kujiequ.exchange"))],
)
def kujiequ_exchange_shop(
    game_id: int | None = Query(default=None, ge=0, le=99),
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        data = fetch_exchange_shop(db, member, game_id=game_id)
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return KujiequExchangeShopOut(
        gold=int(data.get("gold") or 0),
        items=[KujiequExchangeItemOut(**item) for item in data.get("items") or []],
        roles=[KujiequExchangeRoleOut(**r) for r in data.get("roles") or []],
    )


@router.post(
    "/exchange",
    response_model=KujiequExchangeResultOut,
    dependencies=[Depends(require_feature("kujiequ.exchange"))],
)
def kujiequ_do_exchange(
    payload: KujiequExchangeRequest,
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
):
    try:
        out = run_exchange_for_member(
            db,
            member,
            commodity_code=payload.commodity_code,
            game_id=payload.game_id,
            role_id=payload.role_id,
        )
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    item = out.get("item")
    return KujiequExchangeResultOut(
        ok=bool(out.get("ok")),
        message=str(out.get("message") or ""),
        gold=out.get("gold"),
        item=KujiequExchangeItemOut(**item) if isinstance(item, dict) else None,
    )


@router.get(
    "/attendance-calendar",
    response_model=KujiequAttendanceCalendarOut,
    dependencies=[Depends(require_feature("kujiequ.checkin"))],
)
def kujiequ_attendance_calendar(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
    game_code: str = Query(..., min_length=1, max_length=32),
    role_uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """鸣潮 / 战双签到周期日历（第 N 天奖励，非公历）；默认读库，force 回源。"""
    try:
        parsed, role, roles, synced_at, stale = (
            get_kujiequ_attendance_calendar_for_member(
                db,
                member,
                game_code=game_code,
                role_uid=role_uid,
                force=force,
            )
        )
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)

    days = [
        KujiequAttendanceDayOut(
            day=int(d["day"]),
            claimed=bool(d["claimed"]),
            awards=[CheckinAwardItem(**a) for a in (d.get("awards") or [])],
        )
        for d in (parsed.get("days") or [])
        if isinstance(d, dict)
    ]
    return KujiequAttendanceCalendarOut(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        uid=role.role_id,
        role_name=role.role_name,
        claimed_days=int(parsed.get("claimed_days") or 0),
        total_days=int(parsed.get("total_days") or 0),
        has_today_claim=bool(parsed.get("has_today_claim")),
        progress_reliable=bool(parsed.get("progress_reliable", True)),
        days=days,
        roles=[
            KujiequRoleOut(
                game_code=f"game_{r.game_id}",
                game_name=r.game_name,
                uid=r.role_id,
                role_name=r.role_name,
                channel_name=r.server_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


def _ww_box_out(box, role, roles, synced_at, stale: bool) -> WwBoxOut:
    return WwBoxOut(
        uid=box.uid,
        role_id=box.role_id,
        role_name=box.role_name,
        server_id=box.server_id or role.server_id,
        server_name=box.server_name or role.server_name,
        game_code=box.game_code,
        game_name=box.game_name,
        level=box.level,
        world_level=box.world_level,
        active_days=box.active_days,
        role_num=box.role_num,
        achievement_count=box.achievement_count,
        achievement_star=box.achievement_star,
        energy=box.energy,
        max_energy=box.max_energy,
        store_energy=box.store_energy,
        store_energy_limit=box.store_energy_limit,
        store_energy_title=box.store_energy_title,
        store_energy_icon_url=box.store_energy_icon_url,
        liveness=box.liveness,
        liveness_max=box.liveness_max,
        small_count=box.small_count,
        big_count=box.big_count,
        sound_box=box.sound_box,
        weekly_inst_count=box.weekly_inst_count,
        weekly_inst_limit=box.weekly_inst_limit,
        weekly_inst_title=box.weekly_inst_title,
        weekly_inst_icon_url=box.weekly_inst_icon_url,
        rouge_score=box.rouge_score,
        rouge_score_limit=box.rouge_score_limit,
        rouge_title=box.rouge_title,
        rouge_icon_url=box.rouge_icon_url,
        treasure_boxes=[
            WwBoxItemOut(name=i.name, num=i.num, icon_url=i.icon_url)
            for i in box.treasure_boxes
        ],
        phantom_boxes=[
            WwBoxItemOut(name=i.name, num=i.num, icon_url=i.icon_url)
            for i in box.phantom_boxes
        ],
        calabash_level=box.calabash_level,
        calabash_unlock=box.calabash_unlock,
        calabash_max=box.calabash_max,
        calabash_cost=box.calabash_cost,
        roles=[
            KujiequRoleOut(
                game_code=f"game_{r.game_id}",
                game_name=r.game_name,
                uid=r.role_id,
                role_name=r.role_name,
                channel_name=r.server_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


@router.get(
    "/ww/box",
    response_model=WwBoxOut,
    dependencies=[Depends(require_feature("kujiequ.ww"))],
)
def kujiequ_ww_box(
    db: Session = Depends(get_db),
    member: Member = Depends(require_user_member),
    uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """鸣潮资料卡（roleBox）：默认读库二次加工；force 或首次回源落库。"""
    try:
        box, role, roles, synced_at, stale = get_ww_box_for_member(
            db, member, uid, force=force
        )
    except KujiequApiError as exc:
        raise_api_error(exc, KujiequApiError)
    return _ww_box_out(box, role, roles, synced_at, stale)
