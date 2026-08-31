"""塔科夫战局准备房间：固定席位、并集勾选、自由涂鸦画板。"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
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
from app.services.tarkov.game_mode import (
    current_game_mode,
    game_mode_scope,
    parse_game_mode,
)
from app.services.tarkov.tasks import MAP_SLUG_EQUIV_GROUPS

logger = logging.getLogger(__name__)

MARK_PIN = "pin"
MARK_LINE = "line"
MARK_STROKE = "stroke"

SLOT_COUNT = 5
SLOT_MODES = ("pvp", "pve")
_SLOT_ID_RE = re.compile(r"^(?:pve-)?([1-5])$")
MAX_MEMBERS = 8
MEMBER_IDLE_SECONDS = 2 * 60 * 60
MAX_ROOM_PASSWORD_LEN = 32
MAX_UNIQUE_TASKS = 40
MAX_STARTED_TASKS = 400
MAX_STARTED_DONE = 800
OVERLAP_TASK_CAP = 80
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


def slot_public_id(slot: int, game_mode: str = "pvp") -> str:
    n = int(slot)
    if n < 1 or n > SLOT_COUNT:
        return ""
    if parse_game_mode(game_mode) == "pve":
        return f"pve-{n}"
    return str(n)


def slot_index(public_id: str) -> int:
    matched = _SLOT_ID_RE.fullmatch((public_id or "").strip().lower())
    return int(matched.group(1)) if matched else 0


def slot_mode(public_id: str) -> str:
    key = (public_id or "").strip().lower()
    if key.startswith("pve-"):
        return "pve"
    return "pvp"


def slot_ids_for_mode(game_mode: str | None = None) -> tuple[str, ...]:
    mode = parse_game_mode(game_mode) if game_mode is not None else current_game_mode()
    return tuple(slot_public_id(n, mode) for n in range(1, SLOT_COUNT + 1))


SLOT_PUBLIC_IDS = tuple(
    slot_public_id(n, mode)
    for mode in SLOT_MODES
    for n in range(1, SLOT_COUNT + 1)
)


def normalize_slot_id(raw: str) -> str:
    key = (raw or "").strip().lower()
    return key if key in SLOT_PUBLIC_IDS else ""


def is_slot_public_id(public_id: str) -> bool:
    return (public_id or "").strip().lower() in SLOT_PUBLIC_IDS


def normalize_public_id(raw: str) -> str:
    key = (raw or "").strip().lower()
    return key if key in SLOT_PUBLIC_IDS else ""


def room_display_title(room: TarkovRaidRoom) -> str:
    title = (room.title or "").strip()
    if title:
        return title
    if is_slot_public_id(room.public_id):
        return slot_title(slot_index(room.public_id))
    return "房间"


def _room_password_set(room: TarkovRaidRoom) -> bool:
    return bool((room.password_hash or "").strip())


def _assert_join_password(room: TarkovRaidRoom, password: str | None) -> None:
    hashed = (room.password_hash or "").strip()
    if not hashed:
        return
    plain = (password or "").strip()
    if not plain:
        raise RaidRoomError("需要房间密码", 403)
    try:
        ok = verify_password(plain, hashed)
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        raise RaidRoomError("房间密码错误", 403)


def slot_title(slot: int) -> str:
    return f"{slot}号房"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return to_naive(dt).isoformat(timespec="seconds")


def _load_started_ids(row: TarkovRaidRoomMember) -> tuple[bool, list[str]]:
    uploaded = row.task_progress_at is not None
    raw_text = getattr(row, "started_task_ids_json", None) or "[]"
    try:
        parsed = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        parsed = []
    ids = _task_id_list(parsed if isinstance(parsed, list) else [], cap=MAX_STARTED_TASKS)
    return uploaded, ids


def _overlap_payload(
    db: Session,
    room: TarkovRaidRoom,
    occupants: list[TarkovRaidRoomMember],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    progress: list[dict[str, Any]] = []
    overlap_input: list[dict[str, Any]] = []
    for row in occupants:
        uploaded, started = _load_started_ids(row)
        progress.append(
            {
                "user_id": row.user_id,
                "uploaded": uploaded,
                "started_count": len(started) if uploaded else 0,
                "uploaded_at": _iso(row.task_progress_at),
            }
        )
        overlap_input.append(
            {
                "user_id": row.user_id,
                "uploaded": uploaded,
                "started_ids": started if uploaded else [],
            }
        )
    try:
        from app.services.tarkov.tasks import (
            raid_prep_map_task_index,
            raid_prep_room_map_slugs,
        )

        with game_mode_scope(parse_game_mode(room.game_mode or "pvp")):
            catalogs = raid_prep_map_task_index(db)
            map_order = raid_prep_room_map_slugs()
        overlap = build_raid_room_map_overlap(overlap_input, catalogs, map_order)
    except Exception:  # noqa: BLE001
        logger.debug("raid room map overlap skipped", exc_info=True)
        overlap = []
    return progress, overlap


def _display_name(user: User) -> str:
    name = (user.display_name or "").strip()
    return name or user.username


def _task_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text or len(text) > TASK_ID_MAX:
        raise RaidRoomError("任务无效")
    return text


def _task_id_list(raw: list[str] | None, *, cap: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        tid = str(item or "").strip()
        if not tid or len(tid) > TASK_ID_MAX or tid in seen:
            continue
        seen.add(tid)
        out.append(tid)
        if len(out) >= cap:
            break
    return out


def active_started_ids(
    started_ids: list[str] | None,
    done_ids: list[str] | None,
) -> list[str]:
    """进行中去掉已完成，保序。"""
    done = set(_task_id_list(done_ids, cap=MAX_STARTED_DONE))
    return [tid for tid in _task_id_list(started_ids, cap=MAX_STARTED_TASKS) if tid not in done]


def build_raid_room_map_overlap(
    occupants: list[dict[str, Any]],
    catalogs: dict[str, dict[str, str]],
    map_order: list[str],
) -> list[dict[str, Any]]:
    """按图汇总各人进行中任务数。occupants: user_id / uploaded / started_ids。"""
    occupant_count = len(occupants)
    rows: list[dict[str, Any]] = []
    order_index = {slug: i for i, slug in enumerate(map_order)}
    for slug in map_order:
        names = catalogs.get(slug) or {}
        catalog_ids = set(names)
        cells: list[dict[str, Any]] = []
        task_users: dict[str, list[int]] = {}
        with_tasks = 0
        synced = 0
        for occ in occupants:
            uid = int(occ.get("user_id") or 0)
            uploaded = bool(occ.get("uploaded"))
            if uploaded:
                synced += 1
            started = _task_id_list(occ.get("started_ids"), cap=MAX_STARTED_TASKS)
            hit = [tid for tid in started if tid in catalog_ids] if uploaded else []
            if uploaded and hit:
                with_tasks += 1
            cells.append(
                {
                    "user_id": uid,
                    "count": len(hit),
                    "uploaded": uploaded,
                }
            )
            if uploaded:
                for tid in hit:
                    task_users.setdefault(tid, []).append(uid)
        ranked = sorted(
            task_users.items(),
            key=lambda item: (names.get(item[0], ""), item[0]),
        )
        tasks_out = [
            {
                "id": tid,
                "name": names.get(tid, tid),
                "user_ids": uids,
            }
            for tid, uids in ranked[:OVERLAP_TASK_CAP]
        ]
        rows.append(
            {
                "map_slug": slug,
                "with_tasks_count": with_tasks,
                "synced_count": synced,
                "occupant_count": occupant_count,
                "cells": cells,
                "tasks": tasks_out,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["with_tasks_count"]),
            -sum(int(cell["count"]) for cell in row["cells"]),
            order_index.get(str(row["map_slug"]), 99),
            str(row["map_slug"]),
        )
    )
    return rows


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


LOG_PHASE_KINDS = frozenset(
    {
        "map_loading",
        "matching",
        "match_found",
        "raid_starting",
        "raid_started",
        "matching_aborted",
        "raid_exited",
    }
)
LOG_PHASE_KIND_MAX = 32
LOG_PHASE_AT_MAX = 32
LOG_PHASE_RAID_ID_MAX = 16
LOG_PHASE_MAP_LABEL_MAX = 32


def parse_log_phase(payload: dict[str, Any]) -> dict[str, Any] | None:
    """校验本机日志相位广播。无效 kind 返回 None。"""
    kind = str(payload.get("kind") or "").strip()
    if kind not in LOG_PHASE_KINDS or len(kind) > LOG_PHASE_KIND_MAX:
        return None
    raid_id = str(payload.get("raid_id") or "").strip().upper()[:LOG_PHASE_RAID_ID_MAX]
    at = str(payload.get("at") or "").strip()[:LOG_PHASE_AT_MAX]
    map_id = normalize_room_map_slug(str(payload.get("map_id") or ""))
    map_label = str(payload.get("map_label") or "").strip().replace("\n", " ")
    if len(map_label) > LOG_PHASE_MAP_LABEL_MAX:
        map_label = map_label[:LOG_PHASE_MAP_LABEL_MAX]
    return {
        "kind": kind,
        "map_id": map_id,
        "map_label": map_label,
        "raid_id": raid_id,
        "at": at,
    }


def ensure_slot_rooms(db: Session, *, now: datetime | None = None) -> None:
    _purge_legacy_private_rooms(db)
    stamp = to_naive(now or now_naive())
    existing = {
        row.public_id: row
        for row in db.query(TarkovRaidRoom)
        .filter(TarkovRaidRoom.public_id.in_(SLOT_PUBLIC_IDS))
        .all()
    }
    for mode in SLOT_MODES:
        for n in range(1, SLOT_COUNT + 1):
            pid = slot_public_id(n, mode)
            row = existing.get(pid)
            if row is None:
                db.add(
                    TarkovRaidRoom(
                        public_id=pid,
                        title=slot_title(n),
                        map_slug="",
                        game_mode=mode,
                        listed=True,
                        host_user_id=None,
                        host_display_name="",
                        created_at=stamp,
                    )
                )
                continue
            if parse_game_mode(row.game_mode or "pvp") != mode:
                row.game_mode = mode
            if not (row.title or "").strip():
                row.title = slot_title(n)
            row.listed = True
    db.flush()


def _get_room(db: Session, public_id: str) -> TarkovRaidRoom:
    key = normalize_public_id(public_id)
    if not key:
        raise RaidRoomError("房间不存在", 404)
    if is_slot_public_id(key):
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
    room.password_hash = None
    room.game_mode = (
        slot_mode(room.public_id) if is_slot_public_id(room.public_id) else "pvp"
    )
    db.flush()


def _purge_legacy_private_rooms(db: Session) -> None:
    rows = (
        db.query(TarkovRaidRoom)
        .filter(~TarkovRaidRoom.public_id.in_(SLOT_PUBLIC_IDS))
        .all()
    )
    if not rows:
        return
    ids = [int(row.id) for row in rows]
    for model in (
        TarkovRaidRoomMark,
        TarkovRaidRoomKeyBring,
        TarkovRaidRoomObjectiveDone,
        TarkovRaidRoomTaskClaim,
        TarkovRaidRoomMember,
    ):
        (
            db.query(model)
            .filter(model.room_id.in_(ids))
            .delete(synchronize_session=False)
        )
    for row in rows:
        db.delete(row)
    db.flush()


def _room_alive(db: Session, room: TarkovRaidRoom) -> bool:
    return (
        db.query(TarkovRaidRoom.id)
        .filter(TarkovRaidRoom.id == room.id)
        .first()
        is not None
    )


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
    progress, map_overlap = _overlap_payload(db, room, occupants)
    return {
        "public_id": room.public_id,
        "title": room_display_title(room),
        "map_slug": room.map_slug or "",
        "game_mode": parse_game_mode(room.game_mode or "pvp"),
        "listed": True,
        "has_password": _room_password_set(room),
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
        "task_progress": progress,
        "map_overlap": map_overlap,
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
    return {
        "public_id": room.public_id,
        "title": room_display_title(room),
        "map_slug": room.map_slug or "",
        "game_mode": parse_game_mode(room.game_mode or "pvp"),
        "listed": True,
        "has_password": _room_password_set(room),
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
) -> list[dict[str, Any]]:
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
    vacated: list[dict[str, Any]] = []
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
        vacated.append(serialize_room(db, room))
    return vacated


def touch_member(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> None:
    stamp = to_naive(now or now_naive())
    try:
        room = _get_room(db, public_id)
    except RaidRoomError:
        return
    row = _member(db, room.id, user.id)
    if row is None or row.left_at is not None:
        return
    row.last_seen_at = stamp
    db.flush()


def prune_stale_members(
    db: Session,
    room: TarkovRaidRoom,
    *,
    now: datetime,
    online_user_ids: set[int] | None = None,
    keep_user_id: int | None = None,
) -> None:
    """WS 在线集合里的人不踢；其余看 last_seen（WS 心跳），断线满 2 小时才收座位。

    HTTP 拉房间不算心跳。keep_user_id 仅为调用方兼容，不再豁免过期成员。
    """
    del keep_user_id
    stamp = to_naive(now)
    cutoff = stamp - timedelta(seconds=MEMBER_IDLE_SECONDS)
    online = online_user_ids or set()
    rows = (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room.id,
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .all()
    )
    dropped: list[int] = []
    for row in rows:
        if row.user_id in online:
            continue
        seen = to_naive(row.last_seen_at) if row.last_seen_at else None
        if seen is not None and seen >= cutoff:
            continue
        dropped.append(row.user_id)
        db.delete(row)
        _drop_member_contrib(db, room.id, row.user_id)
    if not dropped:
        return
    db.flush()
    if room.host_user_id in dropped:
        _transfer_or_clear(db, room)
    elif _active_member_count(db, room.id) <= 0:
        _clear_slot(db, room)


def set_room_game_mode(
    db: Session,
    public_id: str,
    user: User,
    game_mode: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以改模式", 403)
    mode = parse_game_mode(game_mode)
    if is_slot_public_id(room.public_id):
        raise RaidRoomError("公开桌模式固定，请在顶栏切换后进入对应房间", 403)
    if mode == parse_game_mode(room.game_mode or "pvp"):
        return serialize_room(db, room, viewer=user)
    _wipe_board(db, room.id)
    room.game_mode = mode
    db.flush()
    return serialize_room(db, room, viewer=user)


def set_room_password(
    db: Session,
    public_id: str,
    user: User,
    password: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以设置密码", 403)
    raw = (password or "").strip()
    if not raw:
        room.password_hash = None
    else:
        if len(raw) > MAX_ROOM_PASSWORD_LEN:
            raise RaidRoomError(f"密码最多 {MAX_ROOM_PASSWORD_LEN} 个字符", 400)
        room.password_hash = hash_password(raw)
    db.flush()
    return serialize_room(db, room, viewer=user)


def list_live_rooms(
    db: Session,
    *,
    viewer: User | None = None,
    now: datetime | None = None,
    online_by_public_id: dict[str, set[int]] | None = None,
    game_mode: str | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    mode = parse_game_mode(game_mode) if game_mode is not None else current_game_mode()
    ensure_slot_rooms(db, now=stamp)
    slot_ids = slot_ids_for_mode(mode)
    rows = (
        db.query(TarkovRaidRoom)
        .filter(TarkovRaidRoom.public_id.in_(slot_ids))
        .all()
    )
    rows.sort(key=lambda row: slot_index(row.public_id))
    online_map = online_by_public_id or {}
    for row in rows:
        prune_stale_members(
            db,
            row,
            now=stamp,
            online_user_ids=online_map.get(row.public_id),
            keep_user_id=viewer.id if viewer is not None else None,
        )
    mine = _live_member_room_ids(db, viewer.id) if viewer is not None else set()
    counts = _active_member_counts(db, [int(row.id) for row in rows])
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
        ],
    }


def occupant_public_ids(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(TarkovRaidRoom.public_id)
        .join(TarkovRaidRoomMember, TarkovRaidRoomMember.room_id == TarkovRaidRoom.id)
        .filter(
            TarkovRaidRoomMember.user_id == int(user_id),
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .all()
    )
    return [str(row[0]) for row in rows]


def publish_occupant_key_owns(db: Session, user: User) -> None:
    from app.services.tarkov.raid_room_hub import hub

    for public_id in occupant_public_ids(db, user.id):
        try:
            room = _get_room(db, public_id)
            snap = serialize_room(db, room, viewer=user)
        except RaidRoomError:
            continue
        hub.publish(public_id, {"event": "key_own_change", "snapshot": snap})


def get_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
    online_user_ids: set[int] | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    prune_stale_members(
        db,
        room,
        now=stamp,
        online_user_ids=online_user_ids,
        keep_user_id=user.id,
    )
    if not _room_alive(db, room):
        raise RaidRoomError("房间不存在", 404)
    return serialize_room(db, room, viewer=user, online_user_ids=online_user_ids)


def join_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
    game_mode: str | None = None,
    password: str | None = None,
) -> tuple[dict[str, Any], bool, list[dict[str, Any]]]:
    del game_mode
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    row = _member(db, room.id, user.id)
    already_in = row is not None and row.left_at is None
    if not already_in:
        _assert_join_password(room, password)
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
    return serialize_room(db, room, viewer=user), joined_now, vacated_rooms


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


def set_member_task_progress(
    db: Session,
    public_id: str,
    user: User,
    started_ids: list[str] | None,
    done_ids: list[str] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    row = _require_active_member(db, room, user, now=now)
    active = active_started_ids(started_ids, done_ids)
    row.started_task_ids_json = json.dumps(active, ensure_ascii=False)
    row.task_progress_at = stamp
    db.flush()
    return serialize_room(db, room, viewer=user)


def _insert_claim(
    db: Session,
    room: TarkovRaidRoom,
    user_id: int,
    tid: str,
    stamp: datetime,
) -> bool:
    existing = (
        db.query(TarkovRaidRoomTaskClaim)
        .filter(
            TarkovRaidRoomTaskClaim.room_id == room.id,
            TarkovRaidRoomTaskClaim.task_id == tid,
            TarkovRaidRoomTaskClaim.user_id == user_id,
        )
        .first()
    )
    if existing is not None:
        return False
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
            user_id=user_id,
            created_at=stamp,
        )
    )
    db.flush()
    return True


def seed_claims_from_progress(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int]:
    """房主按在座已上传的进行中任务，把本图目录内的项勾进房间。"""
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以把进行中任务勾到房间", 403)
    slug = normalize_room_map_slug(room.map_slug) or (room.map_slug or "")
    try:
        from app.services.tarkov.tasks import raid_prep_map_task_index

        with game_mode_scope(parse_game_mode(room.game_mode or "pvp")):
            catalogs = raid_prep_map_task_index(db)
    except Exception:  # noqa: BLE001
        catalogs = {}
    catalog = set((catalogs.get(slug) or {}).keys())
    added = 0
    occupants = (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room.id,
            TarkovRaidRoomMember.left_at.is_(None),
        )
        .all()
    )
    for row in occupants:
        uploaded, started = _load_started_ids(row)
        if not uploaded:
            continue
        for tid in started:
            if tid not in catalog:
                continue
            try:
                if _insert_claim(db, room, row.user_id, tid, stamp):
                    added += 1
            except RaidRoomError as exc:
                if exc.status_code == 409 and "已满" in exc.message:
                    continue
                raise
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


def mark_objectives_done(
    db: Session,
    public_id: str,
    user: User,
    pairs: list[tuple[str, str]],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_map(room)
    cleaned: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for task_id, objective_id in pairs:
        tid = _task_id(task_id)
        oid = _objective_id(objective_id)
        if (tid, oid) in seen:
            continue
        seen.add((tid, oid))
        cleaned.append((tid, oid))
    added: list[tuple[str, str]] = []
    if not cleaned:
        return serialize_room(db, room, viewer=user), added
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
    for tid, oid in cleaned:
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
        if existing is not None:
            continue
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
            if unique >= MAX_UNIQUE_OBJECTIVES:
                raise RaidRoomError("本房目标完成记录已满", 409)
            unique += 1
        db.add(
            TarkovRaidRoomObjectiveDone(
                room_id=room.id,
                task_id=tid,
                objective_id=oid,
                user_id=user.id,
                created_at=stamp,
            )
        )
        added.append((tid, oid))
    if added:
        db.flush()
    return serialize_room(db, room, viewer=user), added


def mark_objective_done(
    db: Session,
    public_id: str,
    user: User,
    task_id: str,
    objective_id: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    snap, added = mark_objectives_done(
        db, public_id, user, [(task_id, objective_id)], now=now
    )
    return snap, bool(added)


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
