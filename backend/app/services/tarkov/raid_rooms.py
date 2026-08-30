"""塔科夫战局准备房间：固定席位、并集勾选、自由涂鸦画板。"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.tarkov import (
    TarkovRaidRoom,
    TarkovRaidRoomKeyBring,
    TarkovRaidRoomObjectiveDone,
    TarkovRaidRoomMark,
    TarkovRaidRoomMember,
    TarkovRaidRoomTaskClaim,
)
from app.models.user import User
from app.services.tarkov.key_owns import list_owns_for_users
from app.services.tarkov.tasks import MAP_SLUG_EQUIV_GROUPS

MARK_PIN = "pin"
MARK_LINE = "line"
MARK_STROKE = "stroke"

SLOT_COUNT = 5
SLOT_PUBLIC_IDS = tuple(str(slot) for slot in range(1, SLOT_COUNT + 1))
MAX_MEMBERS = 5
MAX_UNIQUE_TASKS = 40
MAX_UNIQUE_KEYS = 80
MAX_UNIQUE_OBJECTIVES = 200
MAX_PINS = 80
MAX_LINES = 80
MAX_STROKES = 240
MAX_STROKE_POINTS = 160
TASK_ID_MAX = 64
FLOOR_MAX = 64
COORD_MIN = -20000.0
COORD_MAX = 20000.0
LINE_MIN_LEN = 0.5
STROKE_ROUND = 2
_MAP_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class RaidRoomError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_room_map_slug(raw: str) -> str:
    """与战局准备页短 id 对齐（streets / lab / night-factory 等）。"""
    key = (raw or "").strip().lower()
    if not key:
        return ""
    for group in MAP_SLUG_EQUIV_GROUPS:
        if key in group:
            return group[0]
    if _MAP_SLUG_RE.fullmatch(key):
        return key
    return ""


def normalize_slot_id(raw: str) -> str:
    key = (raw or "").strip()
    return key if key in SLOT_PUBLIC_IDS else ""


def slot_title(slot: int) -> str:
    return f"{slot}号房"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return to_naive(dt).isoformat(timespec="seconds")


def _display_name(user: User) -> str:
    name = (user.display_name or "").strip()
    return name or user.username


def _task_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text or len(text) > TASK_ID_MAX:
        raise RaidRoomError("任务无效")
    return text


def _item_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text or len(text) > TASK_ID_MAX:
        raise RaidRoomError("钥匙无效")
    return text


def _objective_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text or len(text) > TASK_ID_MAX:
        raise RaidRoomError("目标无效")
    return text


def _floor(raw: str | None) -> str:
    text = (raw or "").strip()
    if len(text) > FLOOR_MAX:
        raise RaidRoomError("楼层无效")
    return text


def _coord(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RaidRoomError(f"{name} 无效") from exc
    if not math.isfinite(number) or number < COORD_MIN or number > COORD_MAX:
        raise RaidRoomError(f"{name} 无效")
    return number


def _round_coord(value: float) -> float:
    return round(value, STROKE_ROUND)


def normalize_stroke_points(raw: Any) -> list[list[float]]:
    if not isinstance(raw, list) or not raw:
        raise RaidRoomError("笔画无效")
    if len(raw) > MAX_STROKE_POINTS:
        raise RaidRoomError("笔画点过多", 409)
    points: list[list[float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            raise RaidRoomError("笔画无效")
        points.append([_round_coord(_coord(item[0], "x")), _round_coord(_coord(item[1], "z"))])
    return points


def parse_draw_draft(payload: dict[str, Any]) -> dict[str, Any] | None:
    """校验实时涂鸦草稿；空 points 表示抬笔。无效输入返回 None。"""
    try:
        floor = _floor(str(payload.get("floor") or ""))
    except RaidRoomError:
        return None
    raw_points = payload.get("points")
    if raw_points is None or raw_points == []:
        return {"floor": floor, "points": []}
    try:
        return {"floor": floor, "points": normalize_stroke_points(raw_points)}
    except RaidRoomError:
        return None


PLAYER_FIX_NAME_MAX = 200


def parse_player_fix(payload: dict[str, Any]) -> dict[str, Any] | None:
    """校验截图坐标广播；只传数字，不传图片。无效输入返回 None。"""
    try:
        x = _round_coord(_coord(payload.get("x"), "x"))
        y = _round_coord(_coord(payload.get("y"), "y"))
        z = _round_coord(_coord(payload.get("z"), "z"))
    except RaidRoomError:
        return None
    yaw_raw = payload.get("yaw")
    yaw: float | None
    if yaw_raw is None or yaw_raw == "":
        yaw = None
    else:
        try:
            yaw_num = float(yaw_raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(yaw_num):
            return None
        yaw = round(yaw_num, STROKE_ROUND)
    map_id = normalize_room_map_slug(str(payload.get("map_id") or ""))
    file_name = str(payload.get("file_name") or "").strip().replace("\n", " ")
    if len(file_name) > PLAYER_FIX_NAME_MAX:
        file_name = file_name[:PLAYER_FIX_NAME_MAX]
    return {
        "x": x,
        "y": y,
        "z": z,
        "yaw": yaw,
        "map_id": map_id,
        "file_name": file_name,
    }


def ensure_slot_rooms(db: Session, *, now: datetime | None = None) -> None:
    stamp = to_naive(now or now_naive())
    existing = {
        str(row[0])
        for row in db.query(TarkovRaidRoom.public_id).all()
    }
    for slot in range(1, SLOT_COUNT + 1):
        pid = str(slot)
        if pid in existing:
            continue
        db.add(
            TarkovRaidRoom(
                public_id=pid,
                title=slot_title(slot),
                map_slug="",
                host_user_id=None,
                host_display_name="",
                created_at=stamp,
            )
        )
    db.flush()


def _get_room(db: Session, public_id: str) -> TarkovRaidRoom:
    key = normalize_slot_id(public_id)
    if not key:
        raise RaidRoomError("房间不存在", 404)
    ensure_slot_rooms(db)
    room = (
        db.query(TarkovRaidRoom).filter(TarkovRaidRoom.public_id == key).first()
    )
    if room is None:
        raise RaidRoomError("房间不存在", 404)
    return room


def _require_map(room: TarkovRaidRoom) -> None:
    if not (room.map_slug or "").strip():
        raise RaidRoomError("请先选择地图", 409)


def _wipe_board(db: Session, room_id: int) -> None:
    (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.room_id == room_id)
        .delete(synchronize_session=False)
    )
    (
        db.query(TarkovRaidRoomKeyBring)
        .filter(TarkovRaidRoomKeyBring.room_id == room_id)
        .delete(synchronize_session=False)
    )
    (
        db.query(TarkovRaidRoomObjectiveDone)
        .filter(TarkovRaidRoomObjectiveDone.room_id == room_id)
        .delete(synchronize_session=False)
    )
    (
        db.query(TarkovRaidRoomTaskClaim)
        .filter(TarkovRaidRoomTaskClaim.room_id == room_id)
        .delete(synchronize_session=False)
    )


def _clear_slot(db: Session, room: TarkovRaidRoom) -> None:
    _wipe_board(db, room.id)
    (
        db.query(TarkovRaidRoomMember)
        .filter(TarkovRaidRoomMember.room_id == room.id)
        .delete(synchronize_session=False)
    )
    room.host_user_id = None
    room.host_display_name = ""
    room.map_slug = ""
    db.flush()


def _assign_host(room: TarkovRaidRoom, user: User) -> None:
    room.host_user_id = user.id
    room.host_display_name = _display_name(user)


def _transfer_or_clear(db: Session, room: TarkovRaidRoom) -> None:
    nxt = (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room.id,
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .order_by(
            TarkovRaidRoomMember.joined_at.asc(),
            TarkovRaidRoomMember.user_id.asc(),
        )
        .first()
    )
    if nxt is None:
        _clear_slot(db, room)
        return
    room.host_user_id = nxt.user_id
    room.host_display_name = nxt.display_name
    db.flush()


def _member(db: Session, room_id: int, user_id: int) -> TarkovRaidRoomMember | None:
    return (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room_id,
            TarkovRaidRoomMember.user_id == user_id,
        )
        .first()
    )


def _active_member_count(db: Session, room_id: int) -> int:
    return int(
        db.query(func.count())
        .select_from(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room_id,
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .scalar()
        or 0
    )


def _active_member_counts(db: Session, room_ids: list[int]) -> dict[int, int]:
    if not room_ids:
        return {}
    rows = (
        db.query(TarkovRaidRoomMember.room_id, func.count())
        .filter(
            TarkovRaidRoomMember.room_id.in_(room_ids),
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .group_by(TarkovRaidRoomMember.room_id)
        .all()
    )
    return {int(rid): int(cnt) for rid, cnt in rows}


def _require_active_member(
    db: Session,
    room: TarkovRaidRoom,
    user: User,
    *,
    now: datetime | None = None,
) -> TarkovRaidRoomMember:
    row = _member(db, room.id, user.id)
    if row is None or row.left_at is not None:
        raise RaidRoomError("尚未加入该房间", 403)
    del now
    return row


def _user_names(db: Session, user_ids: set[int], fallback: dict[int, str]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.query(User).filter(User.id.in_(user_ids)).all()
    names = {row.id: _display_name(row) for row in rows}
    for uid in user_ids:
        if uid not in names:
            names[uid] = fallback.get(uid) or f"用户{uid}"
    return names


def serialize_mark(row: TarkovRaidRoomMark, author_name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.id,
        "kind": row.kind,
        "floor": row.floor or "",
        "x": row.x,
        "z": row.z,
        "author_user_id": row.author_user_id,
        "author_display_name": author_name,
        "created_at": _iso(row.created_at),
    }
    if row.kind == MARK_LINE:
        payload["x2"] = row.x2
        payload["z2"] = row.z2
    if row.kind == MARK_STROKE:
        payload["x2"] = row.x2
        payload["z2"] = row.z2
        payload["points"] = row.points_json or [[row.x, row.z]]
    return payload


def serialize_room(
    db: Session,
    room: TarkovRaidRoom,
    *,
    viewer: User | None = None,
    online_user_ids: set[int] | None = None,
) -> dict[str, Any]:
    members = (
        db.query(TarkovRaidRoomMember)
        .filter(TarkovRaidRoomMember.room_id == room.id)
        .order_by(TarkovRaidRoomMember.joined_at.asc(), TarkovRaidRoomMember.user_id.asc())
        .all()
    )
    claims = (
        db.query(TarkovRaidRoomTaskClaim)
        .filter(TarkovRaidRoomTaskClaim.room_id == room.id)
        .order_by(TarkovRaidRoomTaskClaim.created_at.asc())
        .all()
    )
    key_brings = (
        db.query(TarkovRaidRoomKeyBring)
        .filter(TarkovRaidRoomKeyBring.room_id == room.id)
        .order_by(TarkovRaidRoomKeyBring.created_at.asc())
        .all()
    )
    objective_dones = (
        db.query(TarkovRaidRoomObjectiveDone)
        .filter(TarkovRaidRoomObjectiveDone.room_id == room.id)
        .order_by(TarkovRaidRoomObjectiveDone.created_at.asc())
        .all()
    )
    marks = (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.room_id == room.id)
        .order_by(TarkovRaidRoomMark.created_at.asc(), TarkovRaidRoomMark.id.asc())
        .all()
    )
    ids: set[int] = set()
    fallback: dict[int, str] = {}
    if room.host_user_id is not None:
        ids.add(room.host_user_id)
        fallback[room.host_user_id] = room.host_display_name
    for row in members:
        ids.add(row.user_id)
        fallback[row.user_id] = row.display_name
    for row in claims:
        ids.add(row.user_id)
    for row in key_brings:
        ids.add(row.user_id)
    for row in objective_dones:
        ids.add(row.user_id)
    for row in marks:
        ids.add(row.author_user_id)
    names = _user_names(db, ids, fallback)
    online = online_user_ids or set()
    viewer_id = viewer.id if viewer is not None else None
    viewer_member = next((row for row in members if viewer_id == row.user_id), None)
    is_member = bool(viewer_member and viewer_member.left_at is None)
    is_host = viewer_id is not None and viewer_id == room.host_user_id
    can_edit = is_member and bool((room.map_slug or "").strip())
    occupants = [row for row in members if row.left_at is None]
    occupant_ids = [row.user_id for row in occupants]
    key_owns = list_owns_for_users(db, occupant_ids)
    return {
        "public_id": room.public_id,
        "title": (room.title or "").strip() or slot_title(int(room.public_id)),
        "map_slug": room.map_slug or "",
        "host_user_id": room.host_user_id,
        "host_display_name": (
            names.get(room.host_user_id) or room.host_display_name
            if room.host_user_id is not None
            else ""
        ),
        "created_at": _iso(room.created_at),
        "member_count": len(occupants),
        "max_members": MAX_MEMBERS,
        "is_host": is_host,
        "is_member": is_member,
        "can_edit": can_edit,
        "occupants": [
            {
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or row.display_name,
                "is_host": row.user_id == room.host_user_id,
                "online": row.user_id in online,
            }
            for row in occupants
        ],
        "members": [
            {
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or row.display_name,
                "is_host": row.user_id == room.host_user_id,
                "in_room": row.left_at is None,
                "online": row.user_id in online,
                "joined_at": _iso(row.joined_at),
            }
            for row in members
        ],
        "claims": [
            {
                "task_id": row.task_id,
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or f"用户{row.user_id}",
                "created_at": _iso(row.created_at),
            }
            for row in claims
        ],
        "key_brings": [
            {
                "item_id": row.item_id,
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or f"用户{row.user_id}",
                "created_at": _iso(row.created_at),
            }
            for row in key_brings
        ],
        "key_owns": [
            {
                "item_id": row.item_id,
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or f"用户{row.user_id}",
                "created_at": _iso(row.created_at),
            }
            for row in key_owns
        ],
        "objective_dones": [
            {
                "task_id": row.task_id,
                "objective_id": row.objective_id,
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or f"用户{row.user_id}",
                "created_at": _iso(row.created_at),
            }
            for row in objective_dones
        ],
        "marks": [
            serialize_mark(row, names.get(row.author_user_id) or f"用户{row.author_user_id}")
            for row in marks
        ],
    }


def serialize_lobby_item(
    db: Session,
    room: TarkovRaidRoom,
    *,
    is_member: bool = False,
    member_count: int | None = None,
    online_user_ids: set[int] | None = None,
) -> dict[str, Any]:
    occupants = (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room.id,
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .order_by(
            TarkovRaidRoomMember.joined_at.asc(),
            TarkovRaidRoomMember.user_id.asc(),
        )
        .all()
    )
    online = online_user_ids or set()
    count = int(member_count) if member_count is not None else len(occupants)
    title = (room.title or "").strip() or slot_title(int(room.public_id or "1"))
    return {
        "public_id": room.public_id,
        "title": title,
        "map_slug": room.map_slug or "",
        "host_user_id": room.host_user_id,
        "host_display_name": room.host_display_name if room.host_user_id else "",
        "member_count": count,
        "max_members": MAX_MEMBERS,
        "is_member": bool(is_member),
        "created_at": _iso(room.created_at),
        "occupants": [
            {
                "user_id": row.user_id,
                "display_name": row.display_name,
                "is_host": row.user_id == room.host_user_id,
                "online": row.user_id in online,
            }
            for row in occupants
        ],
    }


def _drop_member_contrib(db: Session, room_id: int, user_id: int) -> None:
    (
        db.query(TarkovRaidRoomTaskClaim)
        .filter(
            TarkovRaidRoomTaskClaim.room_id == room_id,
            TarkovRaidRoomTaskClaim.user_id == user_id,
        )
        .delete(synchronize_session=False)
    )
    (
        db.query(TarkovRaidRoomKeyBring)
        .filter(
            TarkovRaidRoomKeyBring.room_id == room_id,
            TarkovRaidRoomKeyBring.user_id == user_id,
        )
        .delete(synchronize_session=False)
    )
    (
        db.query(TarkovRaidRoomObjectiveDone)
        .filter(
            TarkovRaidRoomObjectiveDone.room_id == room_id,
            TarkovRaidRoomObjectiveDone.user_id == user_id,
        )
        .delete(synchronize_session=False)
    )


def _live_member_room_ids(db: Session, user_id: int) -> set[int]:
    rows = (
        db.query(TarkovRaidRoomMember.room_id)
        .filter(
            TarkovRaidRoomMember.user_id == user_id,
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .all()
    )
    return {int(row[0]) for row in rows}


def _vacate_other_slots(
    db: Session,
    user: User,
    keep_room_id: int,
    *,
    now: datetime,
) -> list[TarkovRaidRoom]:
    del now
    rows = (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.user_id == user.id,
            TarkovRaidRoomMember.left_at.is_(None),
            TarkovRaidRoomMember.room_id != keep_room_id,
        )
        .all()
    )
    vacated: list[TarkovRaidRoom] = []
    for row in rows:
        room = db.query(TarkovRaidRoom).filter(TarkovRaidRoom.id == row.room_id).first()
        db.delete(row)
        db.flush()
        if room is None:
            continue
        if room.host_user_id == user.id:
            _transfer_or_clear(db, room)
        elif _active_member_count(db, room.id) <= 0:
            _clear_slot(db, room)
        vacated.append(room)
    return vacated


def list_live_rooms(
    db: Session,
    *,
    viewer: User | None = None,
    now: datetime | None = None,
    online_by_public_id: dict[str, set[int]] | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    ensure_slot_rooms(db, now=stamp)
    rows = (
        db.query(TarkovRaidRoom)
        .filter(TarkovRaidRoom.public_id.in_(SLOT_PUBLIC_IDS))
        .all()
    )
    rows.sort(key=lambda row: int(row.public_id))
    mine = _live_member_room_ids(db, viewer.id) if viewer is not None else set()
    counts = _active_member_counts(db, [int(row.id) for row in rows])
    online_map = online_by_public_id or {}
    return {
        "items": [
            serialize_lobby_item(
                db,
                row,
                is_member=row.id in mine,
                member_count=counts.get(int(row.id), 0),
                online_user_ids=online_map.get(row.public_id),
            )
            for row in rows
        ]
    }


def get_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
    online_user_ids: set[int] | None = None,
) -> dict[str, Any]:
    del now
    room = _get_room(db, public_id)
    return serialize_room(db, room, viewer=user, online_user_ids=online_user_ids)


def join_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool, list[dict[str, Any]]]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    vacated_rooms = _vacate_other_slots(db, user, room.id, now=stamp)
    row = _member(db, room.id, user.id)
    joined_now = False
    if row is None:
        if _active_member_count(db, room.id) >= MAX_MEMBERS:
            raise RaidRoomError("房间已满", 409)
        db.add(
            TarkovRaidRoomMember(
                room_id=room.id,
                user_id=user.id,
                display_name=_display_name(user),
                joined_at=stamp,
                last_seen_at=stamp,
            )
        )
        joined_now = True
    elif row.left_at is not None:
        if _active_member_count(db, room.id) >= MAX_MEMBERS:
            raise RaidRoomError("房间已满", 409)
        row.left_at = None
        row.display_name = _display_name(user)
        row.joined_at = stamp
        row.last_seen_at = stamp
        joined_now = True
    else:
        row.display_name = _display_name(user)
        row.last_seen_at = stamp
    if room.host_user_id is None:
        _assign_host(room, user)
    db.flush()
    vacated = [serialize_room(db, vacated_room) for vacated_room in vacated_rooms]
    return serialize_room(db, room, viewer=user), joined_now, vacated


def can_user_edit_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> bool:
    del now
    try:
        room = _get_room(db, public_id)
    except RaidRoomError:
        return False
    if not (room.map_slug or "").strip():
        return False
    row = _member(db, room.id, user.id)
    return row is not None and row.left_at is None


def leave_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    room = _get_room(db, public_id)
    row = _member(db, room.id, user.id)
    if row is not None and row.left_at is None:
        db.delete(row)
        db.flush()
    if room.host_user_id == user.id:
        _transfer_or_clear(db, room)
    elif _active_member_count(db, room.id) <= 0:
        _clear_slot(db, room)
    return serialize_room(db, room, viewer=user)


def reset_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    room = _get_room(db, public_id)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以清空房间", 403)
    _clear_slot(db, room)
    return serialize_room(db, room, viewer=user)


def remove_member(
    db: Session,
    public_id: str,
    host: User,
    target_user_id: int,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    room = _get_room(db, public_id)
    if room.host_user_id != host.id:
        raise RaidRoomError("只有房主可以移除成员", 403)
    uid = int(target_user_id)
    if uid == host.id:
        raise RaidRoomError("不能移除自己", 400)
    row = _member(db, room.id, uid)
    if row is None or row.left_at is not None:
        raise RaidRoomError("该成员不在房间内", 404)
    db.delete(row)
    _drop_member_contrib(db, room.id, uid)
    db.flush()
    return serialize_room(db, room, viewer=host)


def set_room_map(
    db: Session,
    public_id: str,
    user: User,
    map_slug: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以换图", 403)
    slug = normalize_room_map_slug(map_slug)
    if not slug:
        raise RaidRoomError("地图无效")
    if slug == (room.map_slug or ""):
        return serialize_room(db, room, viewer=user)
    _wipe_board(db, room.id)
    room.map_slug = slug
    db.flush()
    return serialize_room(db, room, viewer=user)


def close_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """兼容旧名：清空房间。"""
    return reset_room(db, public_id, user, now=now)


def claim_task(
    db: Session,
    public_id: str,
    user: User,
    task_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    tid = _task_id(task_id)
    belongs = None
    try:
        from app.services.tarkov.tasks import raid_prep_task_belongs_to_map

        belongs = raid_prep_task_belongs_to_map(db, room.map_slug, tid)
    except Exception:  # noqa: BLE001
        belongs = None
    if belongs is False:
        raise RaidRoomError("任务不属于本地图")
    existing = (
        db.query(TarkovRaidRoomTaskClaim)
        .filter(
            TarkovRaidRoomTaskClaim.room_id == room.id,
            TarkovRaidRoomTaskClaim.task_id == tid,
            TarkovRaidRoomTaskClaim.user_id == user.id,
        )
        .first()
    )
    added = False
    if existing is None:
        unique = int(
            db.query(func.count(func.distinct(TarkovRaidRoomTaskClaim.task_id)))
            .filter(TarkovRaidRoomTaskClaim.room_id == room.id)
            .scalar()
            or 0
        )
        task_taken = (
            db.query(TarkovRaidRoomTaskClaim)
            .filter(
                TarkovRaidRoomTaskClaim.room_id == room.id,
                TarkovRaidRoomTaskClaim.task_id == tid,
            )
            .first()
        )
        if task_taken is None and unique >= MAX_UNIQUE_TASKS:
            raise RaidRoomError("本房任务已满", 409)
        db.add(
            TarkovRaidRoomTaskClaim(
                room_id=room.id,
                task_id=tid,
                user_id=user.id,
                created_at=stamp,
            )
        )
        db.flush()
        added = True
    return serialize_room(db, room, viewer=user), added


def claim_tasks(
    db: Session,
    public_id: str,
    user: User,
    task_ids: list[str],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int]:
    """批量认领；已在板上的任务可加入，新任务仍受 40 上限。"""
    added = 0
    seen: set[str] = set()
    for raw in task_ids:
        try:
            tid = _task_id(raw)
        except RaidRoomError:
            continue
        if tid in seen:
            continue
        seen.add(tid)
        try:
            _data, was = claim_task(db, public_id, user, tid, now=now)
        except RaidRoomError as exc:
            if exc.status_code == 409 and "已满" in exc.message:
                continue
            raise
        if was:
            added += 1
    room = _get_room(db, public_id)
    return serialize_room(db, room, viewer=user), added


def unclaim_task(
    db: Session,
    public_id: str,
    user: User,
    task_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    tid = _task_id(task_id)
    row = (
        db.query(TarkovRaidRoomTaskClaim)
        .filter(
            TarkovRaidRoomTaskClaim.room_id == room.id,
            TarkovRaidRoomTaskClaim.task_id == tid,
            TarkovRaidRoomTaskClaim.user_id == user.id,
        )
        .first()
    )
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return serialize_room(db, room, viewer=user), removed


def bring_key(
    db: Session,
    public_id: str,
    user: User,
    item_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    iid = _item_id(item_id)
    existing = (
        db.query(TarkovRaidRoomKeyBring)
        .filter(
            TarkovRaidRoomKeyBring.room_id == room.id,
            TarkovRaidRoomKeyBring.item_id == iid,
            TarkovRaidRoomKeyBring.user_id == user.id,
        )
        .first()
    )
    added = False
    if existing is None:
        unique = int(
            db.query(func.count(func.distinct(TarkovRaidRoomKeyBring.item_id)))
            .filter(TarkovRaidRoomKeyBring.room_id == room.id)
            .scalar()
            or 0
        )
        key_taken = (
            db.query(TarkovRaidRoomKeyBring)
            .filter(
                TarkovRaidRoomKeyBring.room_id == room.id,
                TarkovRaidRoomKeyBring.item_id == iid,
            )
            .first()
        )
        if key_taken is None and unique >= MAX_UNIQUE_KEYS:
            raise RaidRoomError("本房钥匙声明已满", 409)
        db.add(
            TarkovRaidRoomKeyBring(
                room_id=room.id,
                item_id=iid,
                user_id=user.id,
                created_at=stamp,
            )
        )
        db.flush()
        added = True
    return serialize_room(db, room, viewer=user), added


def unbring_key(
    db: Session,
    public_id: str,
    user: User,
    item_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    iid = _item_id(item_id)
    row = (
        db.query(TarkovRaidRoomKeyBring)
        .filter(
            TarkovRaidRoomKeyBring.room_id == room.id,
            TarkovRaidRoomKeyBring.item_id == iid,
            TarkovRaidRoomKeyBring.user_id == user.id,
        )
        .first()
    )
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return serialize_room(db, room, viewer=user), removed


def mark_objective_done(
    db: Session,
    public_id: str,
    user: User,
    task_id: str,
    objective_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    tid = _task_id(task_id)
    oid = _objective_id(objective_id)
    existing = (
        db.query(TarkovRaidRoomObjectiveDone)
        .filter(
            TarkovRaidRoomObjectiveDone.room_id == room.id,
            TarkovRaidRoomObjectiveDone.task_id == tid,
            TarkovRaidRoomObjectiveDone.objective_id == oid,
            TarkovRaidRoomObjectiveDone.user_id == user.id,
        )
        .first()
    )
    added = False
    if existing is None:
        pair_taken = (
            db.query(TarkovRaidRoomObjectiveDone)
            .filter(
                TarkovRaidRoomObjectiveDone.room_id == room.id,
                TarkovRaidRoomObjectiveDone.task_id == tid,
                TarkovRaidRoomObjectiveDone.objective_id == oid,
            )
            .first()
        )
        if pair_taken is None:
            unique = len(
                {
                    (row.task_id, row.objective_id)
                    for row in db.query(
                        TarkovRaidRoomObjectiveDone.task_id,
                        TarkovRaidRoomObjectiveDone.objective_id,
                    )
                    .filter(TarkovRaidRoomObjectiveDone.room_id == room.id)
                    .distinct()
                    .all()
                }
            )
            if unique >= MAX_UNIQUE_OBJECTIVES:
                raise RaidRoomError("本房目标完成记录已满", 409)
        db.add(
            TarkovRaidRoomObjectiveDone(
                room_id=room.id,
                task_id=tid,
                objective_id=oid,
                user_id=user.id,
                created_at=stamp,
            )
        )
        db.flush()
        added = True
    return serialize_room(db, room, viewer=user), added


def unmark_objective_done(
    db: Session,
    public_id: str,
    user: User,
    task_id: str,
    objective_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    tid = _task_id(task_id)
    oid = _objective_id(objective_id)
    row = (
        db.query(TarkovRaidRoomObjectiveDone)
        .filter(
            TarkovRaidRoomObjectiveDone.room_id == room.id,
            TarkovRaidRoomObjectiveDone.task_id == tid,
            TarkovRaidRoomObjectiveDone.objective_id == oid,
            TarkovRaidRoomObjectiveDone.user_id == user.id,
        )
        .first()
    )
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return serialize_room(db, room, viewer=user), removed


def _mark_count(db: Session, room_id: int, kind: str) -> int:
    return int(
        db.query(func.count())
        .select_from(TarkovRaidRoomMark)
        .filter(
            TarkovRaidRoomMark.room_id == room_id,
            TarkovRaidRoomMark.kind == kind,
        )
        .scalar()
        or 0
    )


def add_mark(
    db: Session,
    public_id: str,
    user: User,
    *,
    kind: str,
    floor: str | None,
    x: Any,
    z: Any,
    x2: Any = None,
    z2: Any = None,
    points: Any = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    mark_kind = (kind or "").strip().lower()
    if mark_kind not in {MARK_PIN, MARK_LINE, MARK_STROKE}:
        raise RaidRoomError("记号类型无效")
    if mark_kind == MARK_PIN and _mark_count(db, room.id, MARK_PIN) >= MAX_PINS:
        raise RaidRoomError("钉点已满", 409)
    if mark_kind == MARK_LINE and _mark_count(db, room.id, MARK_LINE) >= MAX_LINES:
        raise RaidRoomError("直线已满", 409)
    if mark_kind == MARK_STROKE and _mark_count(db, room.id, MARK_STROKE) >= MAX_STROKES:
        raise RaidRoomError("笔画已满", 409)
    start_x = _coord(x, "x")
    start_z = _coord(z, "z")
    end_x = end_z = None
    points_json: list[list[float]] | None = None
    if mark_kind == MARK_LINE:
        end_x = _coord(x2, "x2")
        end_z = _coord(z2, "z2")
        if math.hypot(end_x - start_x, end_z - start_z) < LINE_MIN_LEN:
            raise RaidRoomError("直线太短")
    elif mark_kind == MARK_STROKE:
        raw_points = points if isinstance(points, list) and points else [[start_x, start_z]]
        points_json = normalize_stroke_points(raw_points)
        start_x, start_z = points_json[0]
        if len(points_json) > 1:
            end_x, end_z = points_json[-1]
    row = TarkovRaidRoomMark(
        room_id=room.id,
        author_user_id=user.id,
        kind=mark_kind,
        floor=_floor(floor),
        x=start_x,
        z=start_z,
        x2=end_x,
        z2=end_z,
        points_json=points_json,
        created_at=stamp,
    )
    db.add(row)
    db.flush()
    snapshot = serialize_room(db, room, viewer=user)
    mark = next((item for item in snapshot["marks"] if item["id"] == row.id), None)
    if mark is None:
        mark = serialize_mark(row, _display_name(user))
    return snapshot, mark


def remove_mark(
    db: Session,
    public_id: str,
    user: User,
    mark_id: int,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    row = (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.id == mark_id, TarkovRaidRoomMark.room_id == room.id)
        .first()
    )
    if row is None:
        return serialize_room(db, room, viewer=user), False
    if row.author_user_id != user.id and room.host_user_id != user.id:
        raise RaidRoomError("只能删除自己的记号", 403)
    db.delete(row)
    db.flush()
    return serialize_room(db, room, viewer=user), True


def undo_own_mark(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int | None]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    row = (
        db.query(TarkovRaidRoomMark)
        .filter(
            TarkovRaidRoomMark.room_id == room.id,
            TarkovRaidRoomMark.author_user_id == user.id,
        )
        .order_by(TarkovRaidRoomMark.created_at.desc(), TarkovRaidRoomMark.id.desc())
        .first()
    )
    if row is None:
        return serialize_room(db, room, viewer=user), None
    mark_id = row.id
    db.delete(row)
    db.flush()
    return serialize_room(db, room, viewer=user), mark_id


def clear_marks(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_map(room)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以清板", 403)
    (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.room_id == room.id)
        .delete(synchronize_session=False)
    )
    db.flush()
    return serialize_room(db, room, viewer=user)
