"""塔科夫战局准备房间：大厅、并集勾选、自由涂鸦画板。"""

from __future__ import annotations

import math
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.tarkov import (
    TarkovRaidRoom,
    TarkovRaidRoomMark,
    TarkovRaidRoomMember,
    TarkovRaidRoomTaskClaim,
)
from app.models.user import User
from app.services.tarkov.tasks import MAP_SLUG_EQUIV_GROUPS

STATUS_LIVE = "live"
STATUS_ARCHIVED = "archived"
MARK_PIN = "pin"
MARK_LINE = "line"
MARK_STROKE = "stroke"

ROOM_TTL = timedelta(hours=24)
MAX_MEMBERS = 8
MAX_LIVE_HOSTED = 1
MAX_UNIQUE_TASKS = 40
MAX_PINS = 80
MAX_LINES = 80
MAX_STROKES = 240
MAX_STROKE_POINTS = 160
PUBLIC_ID_LEN = 12
TITLE_MAX = 40
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


def new_public_id() -> str:
    return secrets.token_hex(PUBLIC_ID_LEN // 2)


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


def archive_expired_rooms(db: Session, *, now: datetime | None = None) -> int:
    stamp = to_naive(now or now_naive())
    count = (
        db.query(TarkovRaidRoom)
        .filter(
            TarkovRaidRoom.status == STATUS_LIVE,
            TarkovRaidRoom.expire_at <= stamp,
        )
        .update(
            {
                TarkovRaidRoom.status: STATUS_ARCHIVED,
                TarkovRaidRoom.archived_at: stamp,
            },
            synchronize_session=False,
        )
    )
    db.flush()
    return int(count or 0)


def _archive_room(room: TarkovRaidRoom, now: datetime) -> bool:
    if room.status != STATUS_LIVE:
        return False
    room.status = STATUS_ARCHIVED
    room.archived_at = now
    return True


def _ensure_current(room: TarkovRaidRoom, now: datetime) -> bool:
    """若已到期则封存。返回是否刚封存。"""
    if room.status != STATUS_LIVE:
        return False
    if to_naive(room.expire_at) > now:
        return False
    return _archive_room(room, now)


def _get_room(db: Session, public_id: str) -> TarkovRaidRoom:
    key = (public_id or "").strip()
    if not key:
        raise RaidRoomError("房间不存在", 404)
    room = (
        db.query(TarkovRaidRoom).filter(TarkovRaidRoom.public_id == key).first()
    )
    if room is None:
        raise RaidRoomError("房间不存在", 404)
    return room


def _require_live(room: TarkovRaidRoom) -> None:
    if room.status != STATUS_LIVE:
        raise RaidRoomError("房间已留档，仅供查看", 409)


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


def _host_live_count(db: Session, user_id: int) -> int:
    return int(
        db.query(func.count())
        .select_from(TarkovRaidRoom)
        .filter(
            TarkovRaidRoom.host_user_id == user_id,
            TarkovRaidRoom.status == STATUS_LIVE,
        )
        .scalar()
        or 0
    )


def _require_active_member(db: Session, room: TarkovRaidRoom, user: User) -> TarkovRaidRoomMember:
    row = _member(db, room.id, user.id)
    if row is None or row.left_at is not None:
        raise RaidRoomError("尚未加入该房间", 403)
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
    marks = (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.room_id == room.id)
        .order_by(TarkovRaidRoomMark.created_at.asc(), TarkovRaidRoomMark.id.asc())
        .all()
    )
    ids = {room.host_user_id}
    fallback: dict[int, str] = {room.host_user_id: room.host_display_name}
    for row in members:
        ids.add(row.user_id)
        fallback[row.user_id] = row.display_name
    for row in claims:
        ids.add(row.user_id)
    for row in marks:
        ids.add(row.author_user_id)
    names = _user_names(db, ids, fallback)
    online = online_user_ids or set()
    viewer_id = viewer.id if viewer is not None else None
    viewer_member = next((row for row in members if viewer_id == row.user_id), None)
    is_member = bool(viewer_member and viewer_member.left_at is None)
    is_host = viewer_id == room.host_user_id
    can_edit = room.status == STATUS_LIVE and (is_member or is_host)
    return {
        "public_id": room.public_id,
        "title": (room.title or "").strip(),
        "map_slug": room.map_slug,
        "status": room.status,
        "host_user_id": room.host_user_id,
        "host_display_name": names.get(room.host_user_id) or room.host_display_name,
        "created_at": _iso(room.created_at),
        "expire_at": _iso(room.expire_at),
        "archived_at": _iso(room.archived_at),
        "member_count": sum(1 for row in members if row.left_at is None),
        "max_members": MAX_MEMBERS,
        "is_host": is_host,
        "is_member": is_member or is_host,
        "can_edit": can_edit,
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
) -> dict[str, Any]:
    return {
        "public_id": room.public_id,
        "title": (room.title or "").strip(),
        "map_slug": room.map_slug,
        "status": room.status,
        "host_user_id": room.host_user_id,
        "host_display_name": room.host_display_name,
        "member_count": _active_member_count(db, room.id),
        "max_members": MAX_MEMBERS,
        "is_member": bool(is_member),
        "created_at": _iso(room.created_at),
        "expire_at": _iso(room.expire_at),
    }


def _live_member_room_ids(db: Session, user_id: int) -> set[int]:
    rows = (
        db.query(TarkovRaidRoomMember.room_id)
        .join(
            TarkovRaidRoom,
            TarkovRaidRoom.id == TarkovRaidRoomMember.room_id,
        )
        .filter(
            TarkovRaidRoomMember.user_id == user_id,
            TarkovRaidRoomMember.left_at.is_(None),
            TarkovRaidRoom.status == STATUS_LIVE,
        )
        .all()
    )
    return {int(row[0]) for row in rows}


def create_room(
    db: Session,
    user: User,
    *,
    map_slug: str,
    title: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    archive_expired_rooms(db, now=stamp)
    slug = normalize_room_map_slug(map_slug)
    if not slug:
        raise RaidRoomError("地图无效")
    if _host_live_count(db, user.id) >= MAX_LIVE_HOSTED:
        raise RaidRoomError("同时只能主持一个进行中的房间", 409)
    text = (title or "").strip()
    if len(text) > TITLE_MAX:
        raise RaidRoomError(f"标题最多 {TITLE_MAX} 字")
    room = TarkovRaidRoom(
        public_id=new_public_id(),
        title=text,
        map_slug=slug,
        host_user_id=user.id,
        host_display_name=_display_name(user),
        status=STATUS_LIVE,
        created_at=stamp,
        expire_at=stamp + ROOM_TTL,
    )
    db.add(room)
    db.flush()
    db.add(
        TarkovRaidRoomMember(
            room_id=room.id,
            user_id=user.id,
            display_name=_display_name(user),
            joined_at=stamp,
        )
    )
    db.flush()
    return serialize_room(db, room, viewer=user)


def list_live_rooms(
    db: Session,
    *,
    map_slug: str | None = None,
    now: datetime | None = None,
    viewer: User | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    archive_expired_rooms(db, now=stamp)
    query = db.query(TarkovRaidRoom).filter(TarkovRaidRoom.status == STATUS_LIVE)
    slug = normalize_room_map_slug(map_slug or "")
    if slug:
        query = query.filter(TarkovRaidRoom.map_slug == slug)
    rows = query.order_by(TarkovRaidRoom.created_at.desc()).limit(80).all()
    mine = _live_member_room_ids(db, viewer.id) if viewer is not None else set()
    return {
        "items": [
            serialize_lobby_item(db, row, is_member=row.id in mine) for row in rows
        ]
    }


def get_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
    online_user_ids: set[int] | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    archived_now = _ensure_current(room, stamp)
    db.flush()
    return serialize_room(db, room, viewer=user, online_user_ids=online_user_ids), archived_now


def join_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
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
            )
        )
        joined_now = True
    elif row.left_at is not None:
        if _active_member_count(db, room.id) >= MAX_MEMBERS:
            raise RaidRoomError("房间已满", 409)
        row.left_at = None
        row.display_name = _display_name(user)
        row.joined_at = stamp
        joined_now = True
    else:
        row.display_name = _display_name(user)
    db.flush()
    return serialize_room(db, room, viewer=user), joined_now


def leave_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _ensure_current(room, stamp)
    if room.host_user_id == user.id:
        raise RaidRoomError("房主请关闭房间")
    row = _member(db, room.id, user.id)
    if row is not None and row.left_at is None:
        row.left_at = stamp
        db.flush()
    return serialize_room(db, room, viewer=user)


def close_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _ensure_current(room, stamp)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以关闭房间", 403)
    if room.status == STATUS_LIVE:
        _archive_room(room, stamp)
        db.flush()
    return serialize_room(db, room, viewer=user)


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
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
    _require_active_member(db, room, user)
    tid = _task_id(task_id)
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
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
    _require_active_member(db, room, user)
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
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
    _require_active_member(db, room, user)
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
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
    _require_active_member(db, room, user)
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
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
    _require_active_member(db, room, user)
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
    if _ensure_current(room, stamp):
        db.flush()
        raise RaidRoomError("房间已留档，仅供查看", 409)
    _require_live(room)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以清板", 403)
    (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.room_id == room.id)
        .delete(synchronize_session=False)
    )
    db.flush()
    return serialize_room(db, room, viewer=user)
