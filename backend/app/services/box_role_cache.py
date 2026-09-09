"""从 raw 落库记录还原角色列表，读库路径避免再打上游 list_roles。"""

from __future__ import annotations

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
    """最近一条签到/状态记录里的角色名与渠道（按 uid）。"""
    rows = (
        db.query(SklandCheckinLog)
        .filter(
            SklandCheckinLog.member_id == member_id,
            SklandCheckinLog.game_code == GAME_ARKNIGHTS,
        )
        .order_by(SklandCheckinLog.checked_at.desc())
        .all()
    )
    out: dict[str, tuple[str, str]] = {}
    for row in rows:
        uid = str(row.role_uid or "").strip()
        if not uid or uid in out:
            continue
        out[uid] = (
            str(row.role_name or "").strip(),
            str(row.channel_name or "").strip(),
        )
    return out


def skland_arknights_roles_from_raws(
    db: Session, member_id: int
) -> list[SklandRole] | None:
    attendance_rows = (
        db.query(SklandAttendanceRaw)
        .filter(SklandAttendanceRaw.member_id == member_id)
        .order_by(SklandAttendanceRaw.uid)
        .all()
    )
    rogue_rows = (
        db.query(ArknightsRogueRaw)
        .filter(ArknightsRogueRaw.member_id == member_id)
        .order_by(ArknightsRogueRaw.uid)
        .all()
    )
    if not attendance_rows and not rogue_rows:
        return None

    labels = _arknights_labels_from_checkin_logs(db, member_id)
    meta = GAME_META[GAME_ARKNIGHTS]
    seen: set[str] = set()
    roles: list[SklandRole] = []

    def _append(uid: str, role_name: str, channel_name: str) -> None:
        uid = str(uid or "").strip()
        if not uid or uid in seen:
            return
        seen.add(uid)
        log_name, log_channel = labels.get(uid, ("", ""))
        name = (role_name or "").strip() or log_name or uid
        channel = (channel_name or "").strip() or log_channel
        if channel:
            channel = localize_arknights_channel_name(channel)
        roles.append(
            SklandRole(
                game_code=GAME_ARKNIGHTS,
                game_name=meta["name"],
                uid=uid,
                role_name=name,
                channel_name=channel,
            )
        )

    for row in attendance_rows:
        _append(
            str(row.uid),
            str(row.role_name or ""),
            str(row.channel_name or ""),
        )
    for row in rogue_rows:
        _append(str(row.uid), "", "")
    return roles or None


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
