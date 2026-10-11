"""从 raw 落库记录还原角色列表，读库路径避免再打上游 list_roles。"""

from __future__ import annotations

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.arknights_rogue import ArknightsRogueRaw
from app.models.endfield import EndfieldBoxRaw
from app.models.exastris import ExastrisBoxRaw
from app.models.kujiequ import KujiequWwBoxRaw
from app.models.skland import SklandAttendanceRaw, SklandCheckinLog
from app.services.kujiequ.client import GAME_NAMES, GAME_WW, GameRole
from app.services.skland.client import (
    GAME_ARKNIGHTS,
    GAME_ENDFIELD,
    GAME_META,
    SklandRole,
    localize_arknights_channel_name,
)
from app.services.taygedo.client import GAME_NTE, GAME_NTE_NAME, TaygedoRole


def _arknights_labels_from_checkin_logs(
    db: Session, member_id: int
) -> dict[str, tuple[str, str]]:
    """每个 uid 最近一天签到/状态记录里的角色名与渠道（logs 按角色+日唯一）。"""
    log = SklandCheckinLog
    mine = (log.member_id == member_id, log.game_code == GAME_ARKNIGHTS)
    latest = (
        db.query(log.role_uid, func.max(log.checkin_date).label("day"))
        .filter(*mine)
        .group_by(log.role_uid)
        .subquery()
    )
    rows = (
        db.query(log.role_uid, log.role_name, log.channel_name)
        .join(
            latest,
            and_(log.role_uid == latest.c.role_uid, log.checkin_date == latest.c.day),
        )
        .filter(*mine)
        .all()
    )
    out: dict[str, tuple[str, str]] = {}
    for uid, role_name, channel_name in rows:
        uid = str(uid or "").strip()
        if uid:
            out[uid] = (str(role_name or "").strip(), str(channel_name or "").strip())
    return out


def skland_arknights_roles_from_raws(
    db: Session, member_id: int
) -> list[SklandRole] | None:
    attendance_rows = (
        db.query(
            SklandAttendanceRaw.uid,
            SklandAttendanceRaw.role_name,
            SklandAttendanceRaw.channel_name,
        )
        .filter(SklandAttendanceRaw.member_id == member_id)
        .order_by(SklandAttendanceRaw.uid)
        .all()
    )
    rogue_uids = [
        uid
        for (uid,) in db.query(ArknightsRogueRaw.uid)
        .filter(ArknightsRogueRaw.member_id == member_id)
        .distinct()
        .order_by(ArknightsRogueRaw.uid)
    ]
    seen: dict[str, tuple[str, str]] = {}
    for uid, role_name, channel_name in [
        *attendance_rows,
        *((uid, "", "") for uid in rogue_uids),
    ]:
        uid = str(uid or "").strip()
        if uid and uid not in seen:
            seen[uid] = (str(role_name or "").strip(), str(channel_name or "").strip())
    if not seen:
        return None

    # 肉鸽 raw 不带角色名 / 渠道，缺了才去 logs 里找
    labels = (
        _arknights_labels_from_checkin_logs(db, member_id)
        if any(not name or not channel for name, channel in seen.values())
        else {}
    )
    meta = GAME_META[GAME_ARKNIGHTS]
    roles: list[SklandRole] = []
    for uid, (role_name, channel_name) in seen.items():
        log_name, log_channel = labels.get(uid, ("", ""))
        channel = channel_name or log_channel
        roles.append(
            SklandRole(
                game_code=GAME_ARKNIGHTS,
                game_name=meta["name"],
                uid=uid,
                role_name=role_name or log_name or uid,
                channel_name=localize_arknights_channel_name(channel) if channel else channel,
            )
        )
    return roles


def skland_endfield_roles_from_raws(
    db: Session, member_id: int
) -> list[SklandRole] | None:
    rows = (
        db.query(EndfieldBoxRaw.role_id, EndfieldBoxRaw.uid, EndfieldBoxRaw.server_id)
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
        db.query(ExastrisBoxRaw.role_id)
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
        db.query(KujiequWwBoxRaw.role_id)
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
