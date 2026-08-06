"""森空岛：明日方舟盒子与图鉴。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.skland.helpers import _member_or_404
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.schemas import (
    ArknightsAttendanceCalendarOut,
    ArknightsAttendanceDayOut,
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
    SklandRoleOut,
)
from app.schemas.checkin import CheckinAwardItem
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
from app.services.skland_checkin import (
    get_arknights_attendance_calendar_for_member,
    get_arknights_box_for_member,
)
from app.services.skland_client import SklandApiError

router = APIRouter(tags=["skland"])


@router.get(
    "/arknights/attendance-calendar",
    response_model=ArknightsAttendanceCalendarOut,
    dependencies=[Depends(require_feature("skland.checkin"))],
)
def skland_arknights_attendance_calendar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    uid: str | None = Query(default=None, max_length=32),
    force: bool = Query(default=False),
):
    """明日方舟签到周期日历（第 N 天奖励，非公历日期）；默认读库，force 回源。"""
    member = _member_or_404(db, user)
    try:
        parsed, role, roles, synced_at, stale = (
            get_arknights_attendance_calendar_for_member(
                db, member, uid, force=force
            )
        )
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    days = [
        ArknightsAttendanceDayOut(
            day=int(d["day"]),
            claimed=bool(d["claimed"]),
            awards=[CheckinAwardItem(**a) for a in (d.get("awards") or [])],
        )
        for d in (parsed.get("days") or [])
        if isinstance(d, dict)
    ]
    return ArknightsAttendanceCalendarOut(
        uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        claimed_days=int(parsed.get("claimed_days") or 0),
        total_days=int(parsed.get("total_days") or 0),
        has_today_claim=bool(parsed.get("has_today_claim")),
        progress_reliable=bool(parsed.get("progress_reliable", True)),
        days=days,
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
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


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
