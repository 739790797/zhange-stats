"""森空岛：绑定状态、角色预览、手动/自动签到。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.member import Member
from app.models.user import User
from app.schemas import (
    ArknightsBoxCompareOut,
    ArknightsBoxOut,
    ArknightsCatalogOut,
    ArknightsCatalogSyncOut,
    ArknightsCharOut,
    ArknightsCompareCandidateOut,
    ArknightsCompareRoleOut,
    ArknightsCompareRowOut,
    ArknightsOperatorOut,
    ArknightsOwnedCharOut,
    EndfieldBoxOut,
    EndfieldCharOut,
    EndfieldEquipOut,
    EndfieldSkillOut,
    EndfieldWeaponOut,
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
from app.services.arknights_box_compare import (
    build_box_compare,
    list_compare_candidates,
)
from app.services.arknights_catalog import (
    ArknightsCatalogError,
    ensure_catalog,
    get_catalog_meta,
    list_operators,
    sync_from_upstream,
)
from app.services.member_sync import ensure_user_member
from app.services.skland_checkin import (
    bind_skland,
    bind_skland_with_password,
    bind_skland_with_sms,
    get_arknights_box_for_member,
    get_bind_for_member,
    get_endfield_box_for_member,
    preview_roles,
    query_today_for_bind,
    run_checkin_for_member,
    send_skland_sms,
    set_auto_checkin,
    unbind_skland,
)
from app.services.skland_client import SklandApiError
from app.services.skland_qr import poll_qr_bind, start_qr_bind

router = APIRouter(
    prefix="/skland",
    tags=["skland"],
    dependencies=[Depends(require_feature("skland"))],
)


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
    force: bool = Query(default=False),
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
        live = query_today_for_bind(db, bind, force=force)
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
        checkin_hour=int(bind.checkin_hour),
        checkin_minute=int(bind.checkin_minute),
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


@router.get(
    "/arknights/box",
    response_model=ArknightsBoxOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
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
                main_skill_lvl=c.main_skill_lvl,
                skills=[
                    {
                        "skill_id": s.skill_id,
                        "specialize_level": s.specialize_level,
                        "label": s.label,
                    }
                    for s in (c.skills or [])
                ],
                equips=[
                    {
                        "equip_id": e.equip_id,
                        "name": e.name,
                        "level": e.level,
                        "type_icon": e.type_icon,
                        "locked": e.locked,
                    }
                    for e in (c.equips or [])
                ],
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


def _endfield_box_out(box, role, roles, synced_at, stale: bool) -> EndfieldBoxOut:
    return EndfieldBoxOut(
        uid=box.uid,
        role_id=box.role_id,
        server_id=box.server_id,
        name=box.name,
        level=box.level,
        server_name=box.server_name or role.channel_name,
        avatar_url=box.avatar_url,
        char_count=box.char_count,
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
        chars=[
            EndfieldCharOut(
                char_id=c.char_id,
                name=c.name,
                rarity=c.rarity,
                level=c.level,
                evolve_phase=c.evolve_phase,
                potential_level=c.potential_level,
                profession=c.profession,
                property_name=c.property_name,
                weapon_type=c.weapon_type,
                label_type=c.label_type,
                own_ts=c.own_ts,
                gender=c.gender,
                avatar_url=c.avatar_url,
                illustration_url=c.illustration_url,
                property_icon_url=c.property_icon_url,
                weapon=(
                    EndfieldWeaponOut(
                        weapon_id=c.weapon.weapon_id,
                        name=c.weapon.name,
                        icon_url=c.weapon.icon_url,
                        rarity=c.weapon.rarity,
                        level=c.weapon.level,
                        refine_level=c.weapon.refine_level,
                        breakthrough_level=c.weapon.breakthrough_level,
                        weapon_type=c.weapon.weapon_type,
                        gem_id=c.weapon.gem_id,
                        gem_name=c.weapon.gem_name,
                        gem_icon_url=c.weapon.gem_icon_url,
                    )
                    if c.weapon
                    else None
                ),
                skills=[
                    EndfieldSkillOut(
                        skill_id=s.skill_id,
                        name=s.name,
                        skill_type=s.skill_type,
                        type_label=s.type_label,
                        icon_url=s.icon_url,
                        level=s.level,
                        max_level=s.max_level,
                    )
                    for s in (c.skills or [])
                ],
                equips=[
                    EndfieldEquipOut(
                        slot=e.slot,
                        item_id=e.item_id,
                        name=e.name,
                        icon_url=e.icon_url,
                        rarity=e.rarity,
                        level=e.level,
                        refine_level=e.refine_level,
                    )
                    for e in (c.equips or [])
                ],
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


@router.get(
    "/endfield/box",
    response_model=EndfieldBoxOut,
    dependencies=[Depends(require_feature("skland.endfield"))],
)
def skland_endfield_box(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """终末地养成盒：默认读库二次加工；force 或首次回源落库。"""
    member = _member_or_404(db, user)
    try:
        box, role, roles, synced_at, stale = get_endfield_box_for_member(
            db, member, uid, force=force
        )
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _endfield_box_out(box, role, roles, synced_at, stale)


@router.get(
    "/arknights/catalog",
    response_model=ArknightsCatalogOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """干员图鉴（可招募干员全集）。空库时自动从上游同步一次。"""
    _ = user
    try:
        ensure_catalog(db)
    except ArknightsCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    operators = [
        ArknightsOperatorOut(
            char_id=op.char_id,
            name=op.name,
            rarity=op.rarity,
            profession=op.profession,
            profession_label=op.profession_label,
            avatar_url=op.avatar_url,
        )
        for op in list_operators(db)
    ]
    meta = get_catalog_meta(db)
    return ArknightsCatalogOut(
        operators=operators,
        operator_count=len(operators),
        source_version=meta.source_version if meta else None,
        synced_at=meta.synced_at.isoformat() if meta and meta.synced_at else None,
    )


@router.post(
    "/arknights/catalog/sync",
    response_model=ArknightsCatalogSyncOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_catalog_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：从 ArknightsGameResource 同步 character_table。"""
    try:
        result = sync_from_upstream(db)
    except ArknightsCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ArknightsCatalogSyncOut(
        operator_count=int(result["operator_count"]),
        source_version=result.get("source_version"),
        synced_at=result.get("synced_at"),
    )


@router.get(
    "/arknights/box/compare-candidates",
    response_model=list[ArknightsCompareCandidateOut],
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_compare_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """盒子对比可选成员（自己 + 可见好友，含是否已绑森空岛）。"""
    _member_or_404(db, user)
    rows = list_compare_candidates(db, user)
    return [ArknightsCompareCandidateOut(**r) for r in rows]


@router.get(
    "/arknights/box/compare",
    response_model=ArknightsBoxCompareOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_box_compare(
    member_ids: str = Query(..., description="逗号分隔的成员 id，最多 5 人"),
    role_uids: str | None = Query(
        default=None,
        description="可选，格式 memberId:uid,memberId:uid，指定各成员渠道服角色",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """多用户盒子对比：统一图鉴顺序，未拥有不在 owned 中。"""
    _member_or_404(db, user)
    ids: list[int] = []
    for part in member_ids.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效的 member_id: {part}") from exc

    uid_map: dict[int, str] = {}
    if role_uids:
        for part in role_uids.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            mid_raw, _, uid_raw = part.partition(":")
            try:
                mid = int(mid_raw.strip())
            except ValueError:
                continue
            uid = uid_raw.strip()
            if uid:
                uid_map[mid] = uid

    try:
        data = build_box_compare(db, user, ids, role_uids=uid_map)
    except ArknightsCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ArknightsBoxCompareOut(
        catalog=[ArknightsOperatorOut(**c) for c in data["catalog"]],
        catalog_version=data.get("catalog_version"),
        catalog_synced_at=data.get("catalog_synced_at"),
        rows=[
            ArknightsCompareRowOut(
                member_id=r["member_id"],
                nickname=r["nickname"],
                avatar_url=r.get("avatar_url"),
                status=r["status"],
                message=r.get("message"),
                uid=r.get("uid"),
                role_name=r.get("role_name"),
                channel_name=r.get("channel_name"),
                player_name=r.get("player_name"),
                player_level=r.get("player_level"),
                char_count=r.get("char_count") or 0,
                owned={
                    cid: ArknightsOwnedCharOut(**owned)
                    for cid, owned in (r.get("owned") or {}).items()
                },
                roles=[
                    ArknightsCompareRoleOut(**role)
                    for role in (r.get("roles") or [])
                ],
            )
            for r in data["rows"]
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
    return skland_status(db=db, user=user, include_roles=False)


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
    return SklandCheckinResponse(
        skipped=bool(out.get("skipped")),
        ok=out.get("ok"),
        summary=str(out.get("summary") or ""),
        results=[SklandCheckinResultItem(**r) for r in out.get("results") or []],
    )
