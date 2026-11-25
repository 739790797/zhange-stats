"""Arknights role membership and locally verified game names."""

import json
import re
from hashlib import sha256

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.models.arknights import ArknightsBoxSnapshot
from app.models.arknights_stronghold import StrongholdSyncTarget
from app.models.checkin_role_pref import CheckinRolePref
from app.models.skland import SklandAttendanceRaw, SklandBind, SklandCheckinLog
from app.services.checkin.role_prefs import PLATFORM_SKLAND
from app.services.skland.client import GAME_ARKNIGHTS, localize_arknights_channel_name

RoleKey = tuple[int, str, str]  # member, channel, UID
_TAG = re.compile(r"(.+)#[0-9]+\Z")


def joined_arknights_uids(member_id):
    pref = CheckinRolePref
    return select(pref.role_uid).where(
        pref.member_id == member_id,
        pref.platform == PLATFORM_SKLAND,
        pref.game_code == GAME_ARKNIGHTS,
        pref.included.is_(True),
    )


def is_joined_arknights_role(db: Session, member_id: int, uid: str) -> bool:
    return db.scalar(joined_arknights_uids(member_id).where(CheckinRolePref.role_uid == uid)) is not None


def stronghold_binding_key(token_enc: str) -> str:
    return sha256(token_enc.encode()).hexdigest()


def game_role_name(value: object, uid: str | None = None) -> str | None:
    name = value.strip() if isinstance(value, str) else ""
    return name[:96] if name and name not in (uid, "未知角色", "角色名未同步") else None


def prefer_game_role_name(current: object, fallback: object, uid: str) -> str | None:
    name, cached = game_role_name(current, uid), game_role_name(fallback, uid)
    tag = _TAG.fullmatch(cached or "")
    # A tagged name can complete the same nickname, never undo a rename in the binding list.
    return cached if not name or (tag and tag[1] == name) else name


def _channel(channel_id: object, label: object) -> str | None:
    if str(channel_id) in ("1", "2"):
        return str(channel_id)
    name = localize_arknights_channel_name(label if isinstance(label, str) else None)
    if name in ("官服", "官方", "官方服", "鹰角", "鹰角网络"):
        return "1"
    return "2" if name == "B服" else None


def _unresolved(names: dict[RoleKey, str | None]) -> list[tuple[int, str]]:
    return list(
        dict.fromkeys((member, uid) for (member, _, uid), name in names.items() if not _TAG.fullmatch(name or ""))
    )


def _batches(pairs: list[tuple[int, str]]):
    for start in range(0, len(pairs), 200):
        yield pairs[start : start + 200]


def resolve_game_role_names(db: Session, candidates: dict[RoleKey, str | None]) -> dict[RoleKey, str | None]:
    names = {key: game_role_name(name, key[2]) for key, name in candidates.items()}

    def offer(member: int, uid: str, channel: str | None, name: object):
        if channel is None:
            return
        key = (member, channel, uid)
        if key in names:
            names[key] = prefer_game_role_name(names[key], name, uid)

    # Discovery caches the authenticated binding list before the role imports any battle or box data.
    target, bind = StrongholdSyncTarget, SklandBind
    for pairs in _batches(_unresolved(names)):
        for member, channel, uid, name, generation, token_enc in db.execute(
            select(bind.member_id, target.channel_id, target.uid, target.role_name, target.binding_key, bind.token_enc)
            .join(bind, bind.id == target.bind_id)
            .where(tuple_(bind.member_id, target.uid).in_(pairs))
        ):
            key = (member, channel, uid)
            if key in names and generation == stronghold_binding_key(token_enc):
                offer(member, uid, channel, name)

    box = ArknightsBoxSnapshot
    read_boxes = set()

    def offer_box(member: int, uid: str, raw: str):
        read_boxes.add((member, uid))
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(payload, dict) or payload.get("status") != "ok" or str(payload.get("uid")) != uid:
            return
        channel = _channel(payload.get("channel_master_id"), payload.get("channel_name"))
        offer(member, uid, channel, payload.get("role_name"))
        offer(member, uid, channel, payload.get("player_name"))
        roles = payload.get("roles")
        for role in roles if isinstance(roles, list) else []:
            if isinstance(role, dict):
                offer(
                    member,
                    str(role.get("uid")),
                    _channel(role.get("channel_master_id"), role.get("channel_name")),
                    role.get("role_name"),
                )

    for pairs in _batches(_unresolved(names)):
        for member, uid, raw in db.execute(
            select(box.member_id, box.uid, box.payload_json).where(tuple_(box.member_id, box.uid).in_(pairs))
        ):
            offer_box(member, uid, raw)

    # The box selector can display roles from the last binding list even before each role has its own box.
    for pairs in _batches(_unresolved(names)):
        latest = (
            select(
                box.id,
                func.row_number().over(partition_by=box.member_id, order_by=box.synced_at.desc()).label("position"),
            )
            .where(box.member_id.in_({member for member, _ in pairs}))
            .subquery()
        )
        for member, uid, raw in db.execute(
            select(box.member_id, box.uid, box.payload_json)
            .join(latest, box.id == latest.c.id)
            .where(latest.c.position == 1)
        ):
            if (member, uid) not in read_boxes:
                offer_box(member, uid, raw)

    attendance = SklandAttendanceRaw
    for pairs in _batches(_unresolved(names)):
        for member, uid, channel, name in db.execute(
            select(attendance.member_id, attendance.uid, attendance.channel_name, attendance.role_name).where(
                tuple_(attendance.member_id, attendance.uid).in_(pairs)
            )
        ):
            offer(member, uid, _channel(None, channel), name)

    log = SklandCheckinLog
    for pairs in _batches(_unresolved(names)):
        latest = (
            select(
                log.member_id,
                log.role_uid,
                log.channel_name,
                log.role_name,
                func.row_number()
                .over(
                    partition_by=(log.member_id, log.role_uid, log.channel_name),
                    order_by=log.checkin_date.desc(),
                )
                .label("position"),
            )
            .where(log.game_code == GAME_ARKNIGHTS, tuple_(log.member_id, log.role_uid).in_(pairs))
            .subquery()
        )
        for member, uid, channel, name in db.execute(
            select(latest.c.member_id, latest.c.role_uid, latest.c.channel_name, latest.c.role_name).where(
                latest.c.position == 1
            )
        ):
            offer(member, uid, _channel(None, channel), name)
    return names
