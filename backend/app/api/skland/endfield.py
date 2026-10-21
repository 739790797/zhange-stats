"""森空岛：终末地养成盒。"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.skland.helpers import _member_or_404
from app.api.upstream_repo_errors import upstream_repo_not_synced_http_error
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.platform_deps import require_feature
from app.core.rate_limit import platform_limiter
from app.models.user import User
from app.schemas import (
    ArknightsAttendanceDayOut,
    EndfieldAttendanceCalendarOut,
    EndfieldBoxOut,
    EndfieldBoxCompareOut,
    EndfieldCompareCandidateOut,
    EndfieldCompareRowOut,
    EndfieldCompareRoleOut,
    EndfieldCharOut,
    EndfieldEquipOut,
    EndfieldOperatorOut,
    EndfieldSkillOut,
    EndfieldWeaponOut,
    InnPlanOut,
    InnQueryIn,
    InnQueryOut,
    InnTopicsOut,
    SklandRoleOut,
)
from app.schemas.checkin import CheckinAwardItem
from app.services.skland.checkin import (
    get_endfield_attendance_calendar_for_member,
    get_endfield_box_for_member,
)
from app.services.skland.client import SklandApiError
from app.services.skland.endfield_box_compare import (
    EndfieldBoxCompareError,
    build_box_compare,
    list_compare_candidates,
)
from app.services.skland.endfield_catalog import EndfieldCatalogError
from app.services.skland.endfield_inn import build_inn_query, build_plan, list_topics
from app.services.skland.endfield_inn.load import (
    InnDataError,
    InnDataUnavailable,
    InnInvalidInput,
    InnTopicNotFound,
)
from app.services.upstream_repos import RepoError

router = APIRouter(tags=["skland"])
_MEMBER_ID_RE = re.compile(r"^[1-9]\d*$")
_ROLE_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _inn_error(exc: InnDataError | RepoError) -> HTTPException:
    not_synced = upstream_repo_not_synced_http_error(exc)
    if not_synced is not None:
        return not_synced
    if isinstance(exc, InnTopicNotFound):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, (InnDataUnavailable, RepoError)):
        return HTTPException(status_code=503, detail="终末地客栈数据暂不可用")
    if isinstance(exc, InnInvalidInput):
        return HTTPException(status_code=422, detail=exc.message)
    return HTTPException(status_code=503, detail="终末地客栈数据暂不可用")


@router.get(
    "/endfield/inn/topics",
    response_model=InnTopicsOut,
    dependencies=[Depends(require_feature("skland.endfield"))],
)
def skland_endfield_inn_topics() -> InnTopicsOut:
    """客栈主题和扩建选项（读本地 EndfieldData）。"""
    try:
        return InnTopicsOut(**list_topics())
    except (InnDataError, RepoError) as exc:
        raise _inn_error(exc) from exc


@router.get(
    "/endfield/inn/plan",
    response_model=InnPlanOut,
    dependencies=[Depends(require_feature("skland.endfield"))],
)
def skland_endfield_inn_plan(
    topic_id: str = Query(..., min_length=1, max_length=64),
    level: int = Query(..., ge=1, le=4),
    expansions: list[str] | None = Query(default=None, max_length=16),
) -> InnPlanOut:
    """为主题和客栈等级生成菜单、厨师与五星目标估算。"""
    try:
        return InnPlanOut(
            **build_plan(topic_id=topic_id, level=level, expansions=expansions)
        )
    except (InnDataError, RepoError) as exc:
        raise _inn_error(exc) from exc



@router.post(
    "/endfield/inn/query",
    response_model=InnQueryOut,
    dependencies=[Depends(require_feature("skland.endfield"))],
)
def skland_endfield_inn_query(request: InnQueryIn) -> InnQueryOut:
    """查询客栈图鉴、解锁状态与可选主题推荐（不保存用户配置）。"""
    try:
        return InnQueryOut(
            **build_inn_query(
                level=request.level,
                expansions=request.expansions,
                topic_id=request.topic_id,
                topic_stars=request.topic_stars,
                jsspsi_bonus_tier=request.jsspsi_bonus_tier,
            )
        )
    except (InnDataError, RepoError) as exc:
        raise _inn_error(exc) from exc

def _endfield_char_out(char) -> EndfieldCharOut:
    return EndfieldCharOut(
        char_id=char.char_id,
        name=char.name,
        rarity=char.rarity,
        level=char.level,
        evolve_phase=char.evolve_phase,
        potential_level=char.potential_level,
        profession=char.profession,
        property_name=char.property_name,
        weapon_type=char.weapon_type,
        label_type=char.label_type,
        own_ts=char.own_ts,
        gender=char.gender,
        avatar_url=char.avatar_url,
        illustration_url=char.illustration_url,
        property_icon_url=char.property_icon_url,
        weapon=(
            EndfieldWeaponOut(
                weapon_id=char.weapon.weapon_id,
                name=char.weapon.name,
                icon_url=char.weapon.icon_url,
                rarity=char.weapon.rarity,
                level=char.weapon.level,
                refine_level=char.weapon.refine_level,
                breakthrough_level=char.weapon.breakthrough_level,
                weapon_type=char.weapon.weapon_type,
                gem_id=char.weapon.gem_id,
                gem_name=char.weapon.gem_name,
                gem_icon_url=char.weapon.gem_icon_url,
            )
            if char.weapon
            else None
        ),
        skills=[
            EndfieldSkillOut(
                skill_id=skill.skill_id,
                name=skill.name,
                skill_type=skill.skill_type,
                type_label=skill.type_label,
                icon_url=skill.icon_url,
                level=skill.level,
                max_level=skill.max_level,
            )
            for skill in (char.skills or [])
        ],
        equips=[
            EndfieldEquipOut(
                slot=equip.slot,
                item_id=equip.item_id,
                name=equip.name,
                icon_url=equip.icon_url,
                rarity=equip.rarity,
                level=equip.level,
                refine_level=equip.refine_level,
            )
            for equip in (char.equips or [])
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
        chars=[_endfield_char_out(char) for char in box.chars],
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


def _endfield_compare_row_out(row: dict) -> EndfieldCompareRowOut:
    return EndfieldCompareRowOut(
        member_id=row["member_id"],
        nickname=row["nickname"],
        avatar_url=row.get("avatar_url"),
        status=row["status"],
        message=row.get("message"),
        uid=row.get("uid"),
        role_name=row.get("role_name"),
        channel_name=row.get("channel_name"),
        player_level=row.get("player_level"),
        synced_at=row.get("synced_at"),
        char_count=row.get("char_count") or 0,
        owned={
            char_id: _endfield_char_out(char)
            for char_id, char in (row.get("owned") or {}).items()
        },
        roles=[EndfieldCompareRoleOut(**role) for role in row.get("roles", [])],
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
    "/endfield/box/compare-candidates",
    response_model=list[EndfieldCompareCandidateOut],
    dependencies=[Depends(require_feature("skland.endfield"))],
)
def skland_endfield_compare_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """终末地养成对比成员：仅显示仍绑定且有角色记录的站内用户。"""
    _member_or_404(db, user)
    return [
        EndfieldCompareCandidateOut(**row)
        for row in list_compare_candidates(db, user)
    ]


@router.get(
    "/endfield/box/compare",
    response_model=EndfieldBoxCompareOut,
    dependencies=[Depends(require_feature("skland.endfield"))],
)
def skland_endfield_box_compare(
    member_ids: str = Query(..., max_length=256, description="逗号分隔的成员 id，最多 5 人"),
    role_uids: str | None = Query(
        default=None,
        max_length=256,
        description="可选，格式 memberId:uid,memberId:uid，指定各成员终末地角色",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """终末地多用户干员练度对比；仅当前用户可回源，其他用户只读已缓存快照。"""
    platform_limiter.hit(
        f"endfield-box-compare:uid:{user.id}", limit=60, window_sec=600
    )
    _member_or_404(db, user)
    ids: list[int] = []
    for part in member_ids.split(","):
        part = part.strip()
        if not part:
            continue
        if not _MEMBER_ID_RE.fullmatch(part):
            raise HTTPException(status_code=400, detail=f"无效的 member_id: {part}")
        ids.append(int(part))

    uid_map: dict[int, str] = {}
    if role_uids:
        for part in role_uids.split(","):
            part = part.strip()
            if not part:
                continue
            member_raw, sep, uid_raw = part.partition(":")
            member_raw, uid_raw = member_raw.strip(), uid_raw.strip()
            if (
                not sep
                or not _MEMBER_ID_RE.fullmatch(member_raw)
                or not _ROLE_UID_RE.fullmatch(uid_raw)
            ):
                raise HTTPException(status_code=400, detail=f"无效的 role_uids: {part}")
            uid_map[int(member_raw)] = uid_raw

    try:
        data = build_box_compare(db, user, ids, role_uids=uid_map)
    except EndfieldBoxCompareError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except (EndfieldCatalogError, RepoError) as exc:
        not_synced = upstream_repo_not_synced_http_error(exc)
        if not_synced is not None:
            raise not_synced from exc
        raise HTTPException(status_code=503, detail="终末地干员数据暂不可用") from exc

    return EndfieldBoxCompareOut(
        catalog=[EndfieldOperatorOut(**operator) for operator in data["catalog"]],
        catalog_count=data["catalog_count"],
        rows=[_endfield_compare_row_out(row) for row in data["rows"]],
    )


@router.get(
    "/endfield/attendance-calendar",
    response_model=EndfieldAttendanceCalendarOut,
    dependencies=[Depends(require_feature("skland.checkin"))],
)
def skland_endfield_attendance_calendar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    uid: str | None = Query(default=None, max_length=64),
    force: bool = Query(default=False),
):
    """终末地签到周期日历（第 N 天奖励，非公历日期）；默认读库，force 回源。"""
    member = _member_or_404(db, user)
    try:
        parsed, role, roles, synced_at, stale = (
            get_endfield_attendance_calendar_for_member(
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
    return EndfieldAttendanceCalendarOut(
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
