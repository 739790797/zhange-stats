"""从 raw 落库记录还原角色列表，读库路径避免再打上游 list_roles。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.arknights_rogue import ArknightsRogueRaw
from app.models.endfield import EndfieldBoxRaw
from app.models.exastris import ExastrisBoxRaw
from app.models.kujiequ import KujiequWwBoxRaw
from app.models.skland import SklandAttendanceRaw
from app.services.kujiequ_client import GAME_NAMES, GAME_WW, GameRole
from app.services.skland_client import (
    GAME_ARKNIGHTS,
    GAME_ENDFIELD,
    GAME_META,
    SklandRole,
)
from app.services.taygedo_client import GAME_NTE, GAME_NTE_NAME, TaygedoRole


def skland_arknights_roles_from_raws(
    db: Session, member_id: int
) -> list[SklandRole] | None:
    rows = (
        db.query(SklandAttendanceRaw)
        .filter(SklandAttendanceRaw.member_id == member_id)
        .order_by(SklandAttendanceRaw.uid)
        .all()
    )
    if not rows:
        rows = (
            db.query(ArknightsRogueRaw)
            .filter(ArknightsRogueRaw.member_id == member_id)
            .order_by(ArknightsRogueRaw.uid)
            .all()
        )
        if not rows:
            return None
        meta = GAME_META[GAME_ARKNIGHTS]
        seen: set[str] = set()
        roles: list[SklandRole] = []
        for row in rows:
            if row.uid in seen:
                continue
            seen.add(row.uid)
            roles.append(
                SklandRole(
                    game_code=GAME_ARKNIGHTS,
                    game_name=meta["name"],
                    uid=row.uid,
                    role_name=row.uid,
                    channel_name="",
                )
            )
        return roles or None

    meta = GAME_META[GAME_ARKNIGHTS]
    return [
        SklandRole(
            game_code=GAME_ARKNIGHTS,
            game_name=meta["name"],
            uid=row.uid,
            role_name=str(row.role_name or row.uid),
            channel_name=str(row.channel_name or ""),
        )
        for row in rows
    ]


def skland_endfield_roles_from_raws(
    db: Session, member_id: int
) -> list[SklandRole] | None:
    rows = (
        db.query(EndfieldBoxRaw)
        .filter(EndfieldBoxRaw.member_id == member_id)
        .order_by(EndfieldBoxRaw.role_id)
        .all()
    )
    if not rows:
        return None
    meta = GAME_META[GAME_ENDFIELD]
    return [
        SklandRole(
            game_code=GAME_ENDFIELD,
            game_name=meta["name"],
            uid=row.uid or row.role_id,
            role_name=row.uid or row.role_id,
            channel_name="",
            role_id=row.role_id,
            server_id=row.server_id,
        )
        for row in rows
    ]


def taygedo_nte_roles_from_raws(db: Session, member_id: int) -> list[TaygedoRole] | None:
    rows = (
        db.query(ExastrisBoxRaw)
        .filter(ExastrisBoxRaw.member_id == member_id)
        .order_by(ExastrisBoxRaw.role_id)
        .all()
    )
    if not rows:
        return None
    return [
        TaygedoRole(
            game_code=GAME_NTE,
            game_name=GAME_NTE_NAME,
            role_id=row.role_id,
            role_name=row.role_id,
        )
        for row in rows
    ]


def kujiequ_ww_roles_from_raws(db: Session, member_id: int) -> list[GameRole] | None:
    rows = (
        db.query(KujiequWwBoxRaw)
        .filter(KujiequWwBoxRaw.member_id == member_id)
        .order_by(KujiequWwBoxRaw.role_id)
        .all()
    )
    if not rows:
        return None
    game_name = GAME_NAMES[GAME_WW]
    return [
        GameRole(
            game_id=GAME_WW,
            game_name=game_name,
            role_id=row.role_id,
            role_name=row.role_id,
            server_id="",
            server_name="",
            user_id="",
        )
        for row in rows
    ]
