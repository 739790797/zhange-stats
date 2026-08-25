"""森空岛：终末地养成盒。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.skland.helpers import _member_or_404
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.platform_deps import require_feature
from app.models.user import User
from app.schemas import (
    ArknightsAttendanceDayOut,
    EndfieldAttendanceCalendarOut,
    EndfieldBoxOut,
    EndfieldCharOut,
    EndfieldEquipOut,
    EndfieldSkillOut,
    EndfieldWeaponOut,
    SklandRoleOut,
)
from app.schemas.checkin import CheckinAwardItem
from app.services.skland.checkin import (
    get_endfield_attendance_calendar_for_member,
    get_endfield_box_for_member,
)
from app.services.skland.client import SklandApiError

router = APIRouter(tags=["skland"])


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
