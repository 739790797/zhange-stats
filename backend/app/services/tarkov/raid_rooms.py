"""塔科夫联机大厅房间：用户创建、并集勾选、自由涂鸦画板。"""

from __future__ import annotations

import json
import logging
import math
import re
import secrets
import threading
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import exists, func, or_
from sqlalchemy.exc import IntegrityError
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
MARK_TEXT = "text"

SLOT_COUNT = 5
SLOT_MODES = ("pvp", "pve")
_SLOT_ID_RE = re.compile(r"^(?:pve-)?([1-5])$")
_PUBLIC_ID_RE = re.compile(r"^(?:(?:pve-)?[1-5]|[a-z0-9]{8,16})$")
RESERVED_PUBLIC_IDS = frozenset({"solo"})
PUBLIC_ID_LEN = 8
MAX_MEMBERS = 8
MEMBER_IDLE_SECONDS = 2 * 60
MAX_ROOM_TITLE_LEN = 40
MIN_ROOM_PASSWORD_LEN = 4
MAX_ROOM_PASSWORD_LEN = 32
LOBBY_PAGE_SIZE_DEFAULT = 10
LOBBY_PAGE_SIZE_MAX = 50
JOIN_RATE_LIMIT = 10
JOIN_RATE_WINDOW_SEC = 600
LOBBY_RATE_LIMIT = 40
LOBBY_RATE_WINDOW_SEC = 60
MAX_UNIQUE_TASKS = 40
MAX_STARTED_TASKS = 400
MAX_STARTED_DONE = 800
OVERLAP_TASK_CAP = 80
MAX_UNIQUE_KEYS = 80
MAX_UNIQUE_OBJECTIVES = 200
MAX_PINS = 80
MAX_LINES = 80
MAX_STROKES = 240
MAX_TEXTS = 80
MAX_TEXT_LEN = 40
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


_T = TypeVar("_T")
_EFFECTS_KEY = "tarkov_raid_room_effects"
# 入座 / 离座 / 回收在进程内串行到 commit 为止（单 app 副本）；join 另对房间行加锁。
_ROOM_TX_LOCK = threading.RLock()


def _effects(db: Session) -> dict[str, list[Any]]:
    box = db.info.get(_EFFECTS_KEY)
    if box is None:
        box = {"evict": [], "close": []}
        db.info[_EFFECTS_KEY] = box
    return box


def _queue_evict(db: Session, public_id: str, user_id: int) -> None:
    pair = (str(public_id), int(user_id))
    evicts = _effects(db)["evict"]
    if pair not in evicts:
        evicts.append(pair)


def _queue_close(db: Session, public_id: str, final_event: dict[str, Any] | None) -> None:
    _effects(db)["close"].append((str(public_id), final_event))


def take_room_effects(db: Session) -> dict[str, list[Any]]:
    """commit 成功后取走待办（踢 socket / 关房）。"""
    return db.info.pop(_EFFECTS_KEY, None) or {"evict": [], "close": []}


def discard_room_effects(db: Session) -> None:
    db.info.pop(_EFFECTS_KEY, None)


def apply_room_effects(effects: dict[str, list[Any]]) -> None:
    """先按人摘 socket（发 member_leave 告别后 4403），再关掉已解散的房间。"""
    from app.services.tarkov.raid_room_hub import hub

    for public_id, user_id in effects.get("evict") or []:
        hub.evict(public_id, user_id)
    for public_id, final_event in effects.get("close") or []:
        hub.close_room(public_id, payload=final_event)


def run_in_room_tx(db: Session, fn: Callable[[], _T]) -> _T:
    """跑一次房间事务：失败回滚并丢弃待办；commit 之后才动 WS hub。

    撞唯一键（别的进程刚写了同一座位 / 声明）时整笔重跑一次，读到已存在的行即按幂等成功处理。
    不用 SAVEPOINT：pysqlite 下 SAVEPOINT 若开启了事务，RELEASE 就等于提前 COMMIT。
    """
    with _ROOM_TX_LOCK:
        for attempt in range(2):
            try:
                result = fn()
                db.commit()
                break
            except IntegrityError:
                db.rollback()
                discard_room_effects(db)
                if attempt:
                    raise
            except Exception:
                db.rollback()
                discard_room_effects(db)
                raise
    apply_room_effects(take_room_effects(db))
    return result


def normalize_room_map_slug(raw: str) -> str:
    """与联机大厅页短 id 对齐（streets / lab / night-factory 等）。"""
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
    if not key or key in RESERVED_PUBLIC_IDS:
        return ""
    return key if _PUBLIC_ID_RE.fullmatch(key) else ""


def join_rate_limit_keys(ip: str, user_id: int, public_id: str) -> tuple[str, str]:
    pid = normalize_public_id(public_id) or (public_id or "").strip().lower() or "invalid"
    return (
        f"tarkov-raid-join:ip:{ip}:{pid}",
        f"tarkov-raid-join:uid:{int(user_id)}:{pid}",
    )


def lobby_rate_limit_keys(ip: str, user_id: int) -> tuple[str, str]:
    return (
        f"tarkov-raid-lobby:ip:{ip}",
        f"tarkov-raid-lobby:uid:{int(user_id)}",
    )


def room_display_title(room: TarkovRaidRoom) -> str:
    title = (room.title or "").strip()
    if title:
        return title
    if is_slot_public_id(room.public_id):
        return slot_title(slot_index(room.public_id))
    return "房间"


def _room_password_set(room: TarkovRaidRoom) -> bool:
    return bool((room.password_hash or "").strip())


def _is_public_lobby_room(room: TarkovRaidRoom) -> bool:
    return bool(room.listed) and not _room_password_set(room)


def _clip_lobby_page(page: int | None, page_size: int | None) -> tuple[int, int]:
    p = 1 if page is None else int(page)
    if p < 1:
        p = 1
    size = (
        LOBBY_PAGE_SIZE_DEFAULT if page_size is None else int(page_size)
    )
    if size < 1:
        size = 1
    if size > LOBBY_PAGE_SIZE_MAX:
        size = LOBBY_PAGE_SIZE_MAX
    return p, size


def _clean_create_visibility(
    listed: bool, password: str | None
) -> tuple[bool, str]:
    raw = (password or "").strip()
    if listed:
        if raw:
            raise RaidRoomError("公开房间不能设密码", 400)
        return True, ""
    if raw and len(raw) < MIN_ROOM_PASSWORD_LEN:
        raise RaidRoomError(f"密码至少 {MIN_ROOM_PASSWORD_LEN} 个字符", 400)
    if len(raw) > MAX_ROOM_PASSWORD_LEN:
        raise RaidRoomError(f"密码最多 {MAX_ROOM_PASSWORD_LEN} 个字符", 400)
    return False, raw


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
    catalog_ids: set[str] | None = None
    catalogs: dict[str, dict[str, Any]] = {}
    map_order: list[str] = []
    try:
        from app.services.tarkov.tasks import (
            catalog_task_id_set,
            raid_prep_map_task_index,
            raid_prep_room_map_slugs,
        )

        with game_mode_scope(parse_game_mode(room.game_mode or "pvp")):
            catalog_ids = catalog_task_id_set(db)
            catalogs = raid_prep_map_task_index(db)
            map_order = raid_prep_room_map_slugs()
    except Exception:  # noqa: BLE001
        logger.debug("raid room map overlap skipped", exc_info=True)
        catalogs = {}
        map_order = []

    progress: list[dict[str, Any]] = []
    overlap_input: list[dict[str, Any]] = []
    for row in occupants:
        uploaded, started = _load_started_ids(row)
        visible = (
            [tid for tid in started if tid in catalog_ids]
            if catalog_ids is not None
            else started
        )
        progress.append(
            {
                "user_id": row.user_id,
                "uploaded": uploaded,
                "started_count": len(visible) if uploaded else 0,
                "uploaded_at": _iso(row.task_progress_at),
            }
        )
        overlap_input.append(
            {
                "user_id": row.user_id,
                "uploaded": uploaded,
                "started_ids": visible if uploaded else [],
            }
        )
    overlap = (
        build_raid_room_map_overlap(overlap_input, catalogs, map_order)
        if map_order
        else []
    )
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


def catalog_task_meta(raw: Any, tid: str) -> tuple[str, str]:
    """目录项：旧格式是任务名，新格式是 {name, trader_slug}。"""
    if isinstance(raw, dict):
        name = str(raw.get("name") or "").strip() or tid
        trader = str(raw.get("trader_slug") or "").strip()
        return name, trader
    text = str(raw or "").strip()
    return (text or tid), ""


def build_raid_room_map_overlap(
    occupants: list[dict[str, Any]],
    catalogs: dict[str, dict[str, Any]],
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
            key=lambda item: (
                catalog_task_meta(names.get(item[0]), item[0])[0],
                item[0],
            ),
        )
        tasks_out = []
        for tid, uids in ranked[:OVERLAP_TASK_CAP]:
            name, trader_slug = catalog_task_meta(names.get(tid), tid)
            tasks_out.append(
                {
                    "id": tid,
                    "name": name,
                    "trader_slug": trader_slug,
                    "user_ids": uids,
                }
            )
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


_MARK_LABEL_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def normalize_mark_label(raw: Any) -> str:
    if raw is None:
        raw = ""
    if not isinstance(raw, str):
        raise RaidRoomError("文字无效")
    text = _MARK_LABEL_CTRL_RE.sub(" ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise RaidRoomError("文字不能为空")
    if len(text) > MAX_TEXT_LEN:
        raise RaidRoomError("文字过长")
    return text


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
    if not map_id:
        return None
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


LIVE_RAID_PHASE_KINDS = frozenset({"match_found", "raid_starting", "raid_started"})
VIEW_MAP_PHASE_KINDS = frozenset(
    {
        "map_loading",
        "matching",
        "match_found",
        "raid_starting",
        "raid_started",
    }
)


def normalize_raid_id(raw: Any) -> str:
    return str(raw or "").strip().upper()[:LOG_PHASE_RAID_ID_MAX]


def shared_raid_map_slug(
    user_id: int,
    seated_ids: set[int],
    phases: list[dict[str, Any]] | None,
) -> str:
    """自己与另一名在座成员同一 shortId 时，返回该局地图。"""
    rows = phases or []
    mine = next((row for row in rows if int(row.get("user_id") or 0) == user_id), None)
    raid = normalize_raid_id((mine or {}).get("raid_id"))
    if not raid or str((mine or {}).get("kind") or "") not in LIVE_RAID_PHASE_KINDS:
        return ""
    peer = next(
        (
            row
            for row in rows
            if int(row.get("user_id") or 0) != user_id
            and int(row.get("user_id") or 0) in seated_ids
            and str(row.get("kind") or "") in LIVE_RAID_PHASE_KINDS
            and normalize_raid_id(row.get("raid_id")) == raid
        ),
        None,
    )
    if peer is None:
        return ""
    return normalize_room_map_slug(
        str((mine or {}).get("map_id") or peer.get("map_id") or ""),
    )


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


def allocate_public_id(db: Session) -> str:
    for _ in range(12):
        pid = secrets.token_hex(PUBLIC_ID_LEN // 2)
        if pid in RESERVED_PUBLIC_IDS or is_slot_public_id(pid):
            continue
        exists = (
            db.query(TarkovRaidRoom.id)
            .filter(TarkovRaidRoom.public_id == pid)
            .first()
        )
        if exists is None:
            return pid
    raise RaidRoomError("无法分配房间号", 503)


def _default_room_title(user: User) -> str:
    name = _display_name(user).replace("\n", " ").strip() or "房间"
    title = f"{name}的房间"
    if len(title) > MAX_ROOM_TITLE_LEN:
        title = title[:MAX_ROOM_TITLE_LEN]
    return title


def _clean_room_title(raw: str | None, user: User) -> str:
    text = (raw or "").strip().replace("\n", " ")
    if not text:
        return _default_room_title(user)
    return text[:MAX_ROOM_TITLE_LEN]


def _get_room(db: Session, public_id: str, *, for_update: bool = False) -> TarkovRaidRoom:
    key = normalize_public_id(public_id)
    if not key:
        raise RaidRoomError("房间不存在", 404)
    q = db.query(TarkovRaidRoom).filter(TarkovRaidRoom.public_id == key)
    if for_update:
        q = q.with_for_update()
    room = q.first()
    if room is None:
        raise RaidRoomError("房间不存在", 404)
    return room


def _require_view_map(public_id: str, user_id: int) -> str:
    from app.services.tarkov.raid_room_hub import hub

    slug = hub.view_map_of(public_id, int(user_id))
    if not slug:
        raise RaidRoomError("请先选择地图", 409)
    return slug


def note_view_map_from_phase(public_id: str, user_id: int, phase: dict[str, Any]) -> bool:
    """带地图的进图相位只改这个人的查看图。退出和取消匹配不清除。"""
    kind = str(phase.get("kind") or "")
    slug = normalize_room_map_slug(str(phase.get("map_id") or ""))
    if kind not in VIEW_MAP_PHASE_KINDS or not slug:
        return False
    from app.services.tarkov.raid_room_hub import hub

    if hub.view_map_of(public_id, int(user_id)) == slug:
        return False
    hub.set_view_map(public_id, int(user_id), slug)
    return True


def _tasks_on_view_map(db: Session, map_slug: str) -> set[str] | None:
    """当前图在 PVP/PVE 目录里的任务 id。没有可用目录时返回 None。"""
    from app.services.tarkov.game_mode import GAME_MODES
    from app.services.tarkov.tasks import raid_prep_task_ids_for_map

    current = current_game_mode()
    modes = (current, *(mode for mode in GAME_MODES if mode != current))
    saw = False
    found: set[str] = set()
    for mode in modes:
        with game_mode_scope(mode):
            ids = raid_prep_task_ids_for_map(db, map_slug)
        if ids is None:
            continue
        saw = True
        found |= set(ids)
    if not saw:
        return None
    return found


def _view_map_task_ids(db: Session, map_slug: str) -> set[str] | None:
    """认领路径每个请求只解析一次本图目录；目录不可用时返回 None，跳过校验也不打上游。"""
    if not map_slug:
        return None
    try:
        return _tasks_on_view_map(db, map_slug)
    except Exception:  # noqa: BLE001
        logger.debug("raid room view map task ids unavailable", exc_info=True)
        return None


def _member_view_maps(public_id: str, member_ids: set[int]) -> list[dict[str, Any]]:
    """只给在座成员的查看图；离座者的进程内状态在 commit 之后才清。"""
    from app.services.tarkov.raid_room_hub import hub

    return [row for row in hub.view_maps(public_id) if int(row["user_id"]) in member_ids]


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


def _dissolve_room(
    db: Session,
    room: TarkovRaidRoom,
    *,
    final_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """最后一人离开或房主清空：擦掉画板/声明后删行，不留空桌。commit 后关掉房间所有 socket。"""
    _queue_close(db, room.public_id, final_event)
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
    db.flush()
    snap = serialize_room(db, room, viewer=None)
    db.delete(room)
    db.flush()
    return snap


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


def _seated_members(db: Session, room_id: int) -> list[TarkovRaidRoomMember]:
    return (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room_id,
        )
        .order_by(
            TarkovRaidRoomMember.joined_at.asc(),
            TarkovRaidRoomMember.user_id.asc(),
        )
        .all()
    )


def acting_host_user_id(
    host_user_id: int | None,
    seated: list[TarkovRaidRoomMember],
    online_user_ids: set[int] | None,
) -> int:
    """房主在线则仍是房主；房主离线（未交权）则最早入座的在线成员代行换图。"""
    host_id = int(host_user_id) if host_user_id else 0
    seated_ids = {int(row.user_id) for row in seated}
    if online_user_ids is None:
        return host_id if host_id in seated_ids else host_id
    if host_id and host_id in seated_ids and host_id in online_user_ids:
        return host_id
    for row in seated:
        uid = int(row.user_id)
        if uid in online_user_ids:
            return uid
    return 0


def _transfer_or_clear(db: Session, room: TarkovRaidRoom) -> dict[str, Any] | None:
    nxt = (
        db.query(TarkovRaidRoomMember)
        .filter(
            TarkovRaidRoomMember.room_id == room.id,
        )
        .order_by(
            TarkovRaidRoomMember.joined_at.asc(),
            TarkovRaidRoomMember.user_id.asc(),
        )
        .first()
    )
    if nxt is None:
        return _dissolve_room(db, room)
    room.host_user_id = nxt.user_id
    room.host_display_name = nxt.display_name
    db.flush()
    return None


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
    if row is None:
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
        "map_slug": row.map_slug or "",
        "floor": row.floor or "",
        "x": row.x,
        "z": row.z,
        "author_user_id": row.author_user_id,
        "author_display_name": author_name,
        "created_at": _iso(row.created_at),
        "label": row.label or "",
    }
    if row.kind == MARK_LINE:
        payload["x2"] = row.x2
        payload["z2"] = row.z2
    if row.kind == MARK_STROKE:
        payload["x2"] = row.x2
        payload["z2"] = row.z2
        payload["points"] = row.points_json or [[row.x, row.z]]
    return payload


def _serialize_room_preview(
    room: TarkovRaidRoom,
    *,
    member_count: int,
    is_host: bool,
) -> dict[str, Any]:
    """非成员可读字段：标题 / 模式 / 人数 / 是否要密码。不含地图、查看图、棋盘与人员名单。"""
    return {
        "public_id": room.public_id,
        "title": room_display_title(room),
        "map_slug": "",
        "view_maps": [],
        "game_mode": parse_game_mode(room.game_mode or "pvp"),
        "listed": bool(room.listed),
        "has_password": _room_password_set(room),
        "host_user_id": None,
        "host_display_name": "",
        "created_at": _iso(room.created_at),
        "member_count": int(member_count),
        "max_members": MAX_MEMBERS,
        "is_host": bool(is_host),
        "is_member": False,
        "can_edit": False,
        "occupants": [],
        "members": [],
        "claims": [],
        "key_brings": [],
        "key_owns": [],
        "objective_dones": [],
        "marks": [],
        "task_progress": [],
        "map_overlap": [],
    }


def serialize_room(
    db: Session,
    room: TarkovRaidRoom,
    *,
    viewer: User | None,
    online_user_ids: set[int] | None = None,
) -> dict[str, Any]:
    """viewer 是登录用户时，未入座只给预览。viewer=None 是给在座成员广播的全量视图，不能回给 HTTP 调用方。"""
    members = (
        db.query(TarkovRaidRoomMember)
        .filter(TarkovRaidRoomMember.room_id == room.id)
        .order_by(TarkovRaidRoomMember.joined_at.asc(), TarkovRaidRoomMember.user_id.asc())
        .all()
    )
    viewer_id = viewer.id if viewer is not None else None
    viewer_member = next((row for row in members if viewer_id == row.user_id), None)
    is_member = viewer_member is not None
    occupants = members
    is_host = viewer_id is not None and viewer_id == room.host_user_id
    if viewer is not None and not is_member:
        return _serialize_room_preview(
            room,
            member_count=len(occupants),
            is_host=is_host,
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
    viewer_map = ""
    if is_member and viewer_id is not None:
        from app.services.tarkov.raid_room_hub import hub

        viewer_map = hub.view_map_of(room.public_id, int(viewer_id))
    can_edit = is_member and bool(viewer_map)
    occupant_ids = [row.user_id for row in occupants]
    key_owns = list_owns_for_users(db, occupant_ids)
    progress, map_overlap = _overlap_payload(db, room, occupants)
    return {
        "public_id": room.public_id,
        "title": room_display_title(room),
        "map_slug": "",
        "view_maps": _member_view_maps(room.public_id, {int(row.user_id) for row in members}),
        "game_mode": parse_game_mode(room.game_mode or "pvp"),
        "listed": bool(room.listed),
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
                "joined_at": _iso(row.joined_at),
            }
            for row in occupants
        ],
        "members": [
            {
                "user_id": row.user_id,
                "display_name": names.get(row.user_id) or row.display_name,
                "is_host": row.user_id == room.host_user_id,
                "in_room": True,
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


_LOBBY_RAID = frozenset({"match_found", "raid_starting", "raid_started"})
_LOBBY_MATCHING = frozenset({"map_loading", "matching"})


def _lobby_occupant(
    row: TarkovRaidRoomMember,
    *,
    host_id: int | None,
    online: bool,
    phase: dict[str, Any] | None,
    view_map: str,
) -> dict[str, Any]:
    kind = str((phase or {}).get("kind") or "")
    phase_map = str((phase or {}).get("map_id") or "")
    if kind in _LOBBY_RAID or kind in _LOBBY_MATCHING:
        shown = phase_map or view_map
    else:
        shown = view_map
    return {
        "user_id": row.user_id,
        "display_name": row.display_name,
        "is_host": row.user_id == host_id,
        "online": online,
        "joined_at": _iso(row.joined_at),
        "map_slug": shown,
        "phase_kind": kind,
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
        )
        .order_by(
            TarkovRaidRoomMember.joined_at.asc(),
            TarkovRaidRoomMember.user_id.asc(),
        )
        .all()
    )
    online = online_user_ids or set()
    count = int(member_count) if member_count is not None else len(occupants)
    from app.services.tarkov.raid_room_hub import hub

    view_by_user = {
        int(row.get("user_id") or 0): str(row.get("map_slug") or "")
        for row in hub.view_maps(room.public_id)
    }
    phase_by_user = {
        int(row.get("user_id") or 0): row for row in hub.log_phases(room.public_id)
    }
    return {
        "public_id": room.public_id,
        "title": room_display_title(room),
        "map_slug": "",
        "game_mode": parse_game_mode(room.game_mode or "pvp"),
        "listed": bool(room.listed),
        "has_password": _room_password_set(room),
        "host_user_id": room.host_user_id,
        "host_display_name": room.host_display_name if room.host_user_id else "",
        "member_count": count,
        "max_members": MAX_MEMBERS,
        "is_member": bool(is_member),
        "created_at": _iso(room.created_at),
        "occupants": [
            _lobby_occupant(
                row,
                host_id=room.host_user_id,
                online=row.user_id in online,
                phase=phase_by_user.get(row.user_id),
                view_map=view_by_user.get(row.user_id) or "",
            )
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
    (
        db.query(TarkovRaidRoomMark)
        .filter(
            TarkovRaidRoomMark.room_id == room_id,
            TarkovRaidRoomMark.author_user_id == user_id,
        )
        .delete(synchronize_session=False)
    )


def _remove_member(db: Session, room: TarkovRaidRoom, row: TarkovRaidRoomMember) -> None:
    """离座的唯一出口（离开 / 踢人 / 回收 / 换房）：删座位和此人的声明、标记；commit 后再摘 socket。"""
    uid = int(row.user_id)
    _drop_member_contrib(db, room.id, uid)
    db.delete(row)
    db.flush()
    _queue_evict(db, room.public_id, uid)


def _settle_room(
    db: Session, room: TarkovRaidRoom, *, departed: Iterable[int]
) -> dict[str, Any] | None:
    """有人离座后：房主走了交给最早入座的人，没人了就解散。解散时返回最后一份快照。"""
    if not _room_alive(db, room):
        return None
    gone = {int(uid) for uid in departed}
    if room.host_user_id is not None and int(room.host_user_id) in gone:
        return _transfer_or_clear(db, room)
    if _active_member_count(db, room.id) <= 0:
        return _dissolve_room(db, room)
    return None


def _live_member_room_ids(db: Session, user_id: int) -> set[int]:
    rows = (
        db.query(TarkovRaidRoomMember.room_id)
        .filter(
            TarkovRaidRoomMember.user_id == user_id,
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
            TarkovRaidRoomMember.room_id != keep_room_id,
        )
        .all()
    )
    vacated: list[dict[str, Any]] = []
    for row in rows:
        room = db.query(TarkovRaidRoom).filter(TarkovRaidRoom.id == row.room_id).first()
        if room is None:
            db.delete(row)
            db.flush()
            continue
        _remove_member(db, room, row)
        dissolved = _settle_room(db, room, departed=[user.id])
        vacated.append(
            dissolved if dissolved is not None else serialize_room(db, room, viewer=None)
        )
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
    if row is None:
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
    """WS 在线集合里的人不踢；其余看 last_seen（WS 心跳），断线满 2 分钟才收座位。

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
        _remove_member(db, room, row)
    if dropped:
        _settle_room(db, room, departed=dropped)


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
    if mode == parse_game_mode(room.game_mode or "pvp"):
        return serialize_room(db, room, viewer=user)
    _wipe_board(db, room.id)
    room.game_mode = mode
    db.flush()
    return serialize_room(db, room, viewer=user)


def get_my_live_room(
    db: Session,
    viewer: User,
    *,
    now: datetime | None = None,
    online_by_public_id: dict[str, set[int]] | None = None,
) -> dict[str, Any] | None:
    stamp = to_naive(now or now_naive())
    room_ids = _live_member_room_ids(db, viewer.id)
    if not room_ids:
        return None
    rows = (
        db.query(TarkovRaidRoom)
        .filter(TarkovRaidRoom.id.in_(room_ids))
        .order_by(TarkovRaidRoom.id.asc())
        .all()
    )
    online_map = online_by_public_id or {}
    for row in rows:
        prune_stale_members(
            db,
            row,
            now=stamp,
            online_user_ids=online_map.get(row.public_id),
            keep_user_id=viewer.id,
        )
        if not _room_alive(db, row):
            continue
        if _active_member_count(db, row.id) <= 0:
            _dissolve_room(db, row)
            continue
        if row.id not in _live_member_room_ids(db, viewer.id):
            continue
        return serialize_lobby_item(
            db,
            row,
            is_member=True,
            member_count=_active_member_count(db, row.id),
            online_user_ids=online_map.get(row.public_id),
        )
    return None


def prune_idle_rooms(
    db: Session,
    *,
    now: datetime,
    online_by_public_id: dict[str, set[int]] | None = None,
    keep_user_id: int | None = None,
) -> None:
    """只加载可能过期的房间，避免大厅列表全表 prune。"""
    stamp = to_naive(now)
    cutoff = stamp - timedelta(seconds=MEMBER_IDLE_SECONDS)
    room_ids = [
        int(row[0])
        for row in (
            db.query(TarkovRaidRoomMember.room_id)
            .filter(
                or_(
                    TarkovRaidRoomMember.last_seen_at.is_(None),
                    TarkovRaidRoomMember.last_seen_at < cutoff,
                )
            )
            .distinct()
            .all()
        )
    ]
    if not room_ids:
        return
    online_map = online_by_public_id or {}
    rows = (
        db.query(TarkovRaidRoom)
        .filter(TarkovRaidRoom.id.in_(room_ids))
        .all()
    )
    for row in rows:
        prune_stale_members(
            db,
            row,
            now=stamp,
            online_user_ids=online_map.get(row.public_id),
            keep_user_id=keep_user_id,
        )
        if not _room_alive(db, row):
            continue
        if _active_member_count(db, row.id) <= 0:
            _dissolve_room(db, row)


def list_live_rooms(
    db: Session,
    *,
    viewer: User | None = None,
    now: datetime | None = None,
    online_by_public_id: dict[str, set[int]] | None = None,
    game_mode: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    stamp = to_naive(now or now_naive())
    mode = parse_game_mode(game_mode) if game_mode is not None else current_game_mode()
    page_n, size_n = _clip_lobby_page(page, page_size)
    online_map = online_by_public_id or {}
    prune_idle_rooms(
        db,
        now=stamp,
        online_by_public_id=online_map,
        keep_user_id=viewer.id if viewer is not None else None,
    )
    has_occupant = (
        exists()
        .where(TarkovRaidRoomMember.room_id == TarkovRaidRoom.id)
    )
    q = db.query(TarkovRaidRoom).filter(
        TarkovRaidRoom.listed.is_(True),
        TarkovRaidRoom.game_mode == mode,
        or_(
            TarkovRaidRoom.password_hash.is_(None),
            TarkovRaidRoom.password_hash == "",
        ),
        has_occupant,
    )
    total = int(q.count())
    start = (page_n - 1) * size_n
    sliced = (
        q.order_by(TarkovRaidRoom.created_at.desc(), TarkovRaidRoom.id.desc())
        .offset(start)
        .limit(size_n)
        .all()
    )
    mine_ids = _live_member_room_ids(db, viewer.id) if viewer is not None else set()
    counts = _active_member_counts(db, [int(row.id) for row in sliced])
    mine_item = (
        get_my_live_room(
            db,
            viewer,
            now=stamp,
            online_by_public_id=online_map,
        )
        if viewer is not None
        else None
    )
    return {
        "items": [
            serialize_lobby_item(
                db,
                row,
                is_member=row.id in mine_ids,
                member_count=counts.get(int(row.id), 0),
                online_user_ids=online_map.get(row.public_id),
            )
            for row in sliced
        ],
        "page": page_n,
        "page_size": size_n,
        "total": total,
        "mine": mine_item,
    }


def occupant_public_ids(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(TarkovRaidRoom.public_id)
        .join(TarkovRaidRoomMember, TarkovRaidRoomMember.room_id == TarkovRaidRoom.id)
        .filter(
            TarkovRaidRoomMember.user_id == int(user_id),
        )
        .all()
    )
    return [str(row[0]) for row in rows]


def _room_key_owns(db: Session, room: TarkovRaidRoom) -> list[dict[str, Any]]:
    members = _seated_members(db, room.id)
    fallback = {int(row.user_id): row.display_name for row in members}
    names = _user_names(db, set(fallback), fallback)
    return [
        {
            "item_id": row.item_id,
            "user_id": row.user_id,
            "display_name": names.get(row.user_id) or f"用户{row.user_id}",
            "created_at": _iso(row.created_at),
        }
        for row in list_owns_for_users(db, list(fallback))
    ]


def publish_occupant_key_owns(db: Session, user: User) -> None:
    from app.services.tarkov.raid_room_hub import hub

    for public_id in occupant_public_ids(db, user.id):
        try:
            room = _get_room(db, public_id)
        except RaidRoomError:
            continue
        hub.publish(
            public_id,
            {
                "event": "key_own_change",
                "key_owns": _room_key_owns(db, room),
                "online_user_ids": list(hub.online_user_ids(public_id)),
                "online_clients": hub.online_clients(public_id),
            },
        )


def get_room(
    db: Session,
    public_id: str,
    user: User | None,
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
        keep_user_id=user.id if user is not None else None,
    )
    if not _room_alive(db, room):
        raise RaidRoomError("房间不存在", 404)
    if user is None:
        return _serialize_room_preview(
            room,
            member_count=_active_member_count(db, room.id),
            is_host=False,
        )
    return serialize_room(db, room, viewer=user, online_user_ids=online_user_ids)


def create_room(
    db: Session,
    user: User,
    *,
    now: datetime | None = None,
    title: str | None = None,
    password: str | None = None,
    listed: bool = True,
    game_mode: str | None = None,
) -> tuple[dict[str, Any], bool, list[dict[str, Any]]]:
    stamp = to_naive(now or now_naive())
    mode = parse_game_mode(game_mode) if game_mode is not None else current_game_mode()
    pid = allocate_public_id(db)
    is_listed, raw_password = _clean_create_visibility(bool(listed), password)
    room = TarkovRaidRoom(
        public_id=pid,
        title=_clean_room_title(title, user),
        map_slug="",
        game_mode=mode,
        listed=is_listed,
        password_hash=hash_password(raw_password) if raw_password else None,
        host_user_id=None,
        host_display_name="",
        created_at=stamp,
    )
    db.add(room)
    db.flush()
    return join_room(
        db,
        pid,
        user,
        now=stamp,
        password=raw_password or None,
    )


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
    room = _get_room(db, public_id, for_update=True)
    row = _member(db, room.id, user.id)
    already_in = row is not None
    if not already_in:
        _assert_join_password(room, password)
    vacated_rooms = _vacate_other_slots(db, user, room.id, now=stamp)
    row = _member(db, room.id, user.id)
    joined_now = False
    if row is None:
        if _locked_member_count(db, room.id) >= MAX_MEMBERS:
            raise RaidRoomError("房间已满", 409)
        _insert_member(db, room, user, stamp)
        joined_now = True
    else:
        row.display_name = _display_name(user)
        row.last_seen_at = stamp
    if room.host_user_id is None:
        _assign_host(room, user)
    db.flush()
    return serialize_room(db, room, viewer=user), joined_now, vacated_rooms


def _locked_member_count(db: Session, room_id: int) -> int:
    """锁定读：多 worker 时也能数到别人刚提交的座位（SQLite 忽略 FOR UPDATE）。"""
    return len(
        db.query(TarkovRaidRoomMember.user_id)
        .filter(TarkovRaidRoomMember.room_id == room_id)
        .with_for_update()
        .all()
    )


def _insert_member(db: Session, room: TarkovRaidRoom, user: User, stamp: datetime) -> None:
    db.add(
        TarkovRaidRoomMember(
            room_id=room.id,
            user_id=user.id,
            display_name=_display_name(user),
            joined_at=stamp,
            last_seen_at=stamp,
        )
    )
    db.flush()


def is_room_member(db: Session, public_id: str, user: User) -> bool:
    try:
        room = _get_room(db, public_id)
    except RaidRoomError:
        return False
    return _member(db, room.id, user.id) is not None


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
    row = _member(db, room.id, user.id)
    if row is None:
        return False
    from app.services.tarkov.raid_room_hub import hub

    return bool(hub.view_map_of(room.public_id, user.id))


def leave_room(
    db: Session,
    public_id: str,
    user: User,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """返回 (给离开者的视图, 给仍在座成员广播的快照)；房间随之解散时第二项为 None。"""
    del now
    room = _get_room(db, public_id)
    row = _member(db, room.id, user.id)
    if row is not None:
        _remove_member(db, room, row)
    dissolved = _settle_room(db, room, departed=[user.id])
    if dissolved is not None:
        return dissolved, None
    return serialize_room(db, room, viewer=user), serialize_room(db, room, viewer=None)


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
    return _dissolve_room(db, room, final_event={"event": "reset"})


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
    if row is None:
        raise RaidRoomError("该成员不在房间内", 404)
    _remove_member(db, room, row)
    return serialize_room(db, room, viewer=host)


def transfer_host(
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
        raise RaidRoomError("只有房主可以转让房主", 403)
    uid = int(target_user_id)
    if uid == host.id:
        raise RaidRoomError("不能转让给自己", 400)
    row = _member(db, room.id, uid)
    if row is None:
        raise RaidRoomError("该成员不在房间内", 404)
    room.host_user_id = row.user_id
    room.host_display_name = row.display_name
    db.flush()
    return serialize_room(db, room, viewer=host)


def set_room_map(
    db: Session,
    public_id: str,
    user: User,
    map_slug: str,
    *,
    now: datetime | None = None,
    online_user_ids: set[int] | None = None,
    log_phases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """写入这个人自己的查看图。不改房间、不清画板。"""
    del online_user_ids, log_phases
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = normalize_room_map_slug(map_slug)
    if not slug:
        raise RaidRoomError("地图无效")
    from app.services.tarkov.raid_room_hub import hub

    hub.set_view_map(room.public_id, user.id, slug)
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
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    tid = _task_id(task_id)
    map_ids = _view_map_task_ids(db, slug)
    if map_ids is not None and tid not in map_ids:
        raise RaidRoomError("任务不属于本地图")
    added = _insert_claim(db, room, user.id, tid, stamp, map_ids=map_ids)
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
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    map_ids = _view_map_task_ids(db, slug)
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
        if map_ids is not None and tid not in map_ids:
            raise RaidRoomError("任务不属于本地图")
        try:
            was = _insert_claim(db, room, user.id, tid, stamp, map_ids=map_ids)
        except RaidRoomError as exc:
            if exc.status_code == 409 and "已满" in exc.message:
                continue
            raise
        if was:
            added += 1
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


def _unique_claims_for_map(db: Session, room_id: int, map_ids: set[str] | None) -> int:
    rows = (
        db.query(TarkovRaidRoomTaskClaim.task_id)
        .filter(TarkovRaidRoomTaskClaim.room_id == room_id)
        .distinct()
        .all()
    )
    ids = [str(row[0]) for row in rows]
    if map_ids is None:
        return len(ids)
    return sum(1 for tid in ids if tid in map_ids)


def _insert_claim(
    db: Session,
    room: TarkovRaidRoom,
    user_id: int,
    tid: str,
    stamp: datetime,
    *,
    map_ids: set[str] | None = None,
) -> bool:
    """map_ids 由调用方每次请求解析一次（见 _view_map_task_ids），None 时按全房计数。"""
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
    unique = _unique_claims_for_map(db, room.id, map_ids)
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
    """按自己已上传的进行中任务，把当前查看图目录内的项勾进房间。"""
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    try:
        from app.services.tarkov.tasks import raid_prep_map_task_index

        with game_mode_scope(parse_game_mode(room.game_mode or "pvp")):
            catalogs = raid_prep_map_task_index(db)
    except Exception:  # noqa: BLE001
        catalogs = {}
    catalog = set((catalogs.get(slug) or {}).keys())
    row = _member(db, room.id, user.id)
    uploaded, started = _load_started_ids(row) if row is not None else (False, [])
    added = 0
    if uploaded:
        map_ids = _view_map_task_ids(db, slug)
        for tid in started:
            if tid not in catalog:
                continue
            try:
                if _insert_claim(db, room, user.id, tid, stamp, map_ids=map_ids):
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
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_view_map(room.public_id, user.id)
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
    _require_view_map(room.public_id, user.id)
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
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    _require_view_map(room.public_id, user.id)
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
    _require_view_map(room.public_id, user.id)
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
    _require_view_map(room.public_id, user.id)
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


def _mark_count(db: Session, room_id: int, kind: str, map_slug: str) -> int:
    return int(
        db.query(func.count())
        .select_from(TarkovRaidRoomMark)
        .filter(
            TarkovRaidRoomMark.room_id == room_id,
            TarkovRaidRoomMark.kind == kind,
            TarkovRaidRoomMark.map_slug == map_slug,
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
    label: str | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    stamp = to_naive(now or now_naive())
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    mark_kind = (kind or "").strip().lower()
    if mark_kind not in {MARK_PIN, MARK_LINE, MARK_STROKE, MARK_TEXT}:
        raise RaidRoomError("记号类型无效")
    if mark_kind == MARK_PIN and _mark_count(db, room.id, MARK_PIN, slug) >= MAX_PINS:
        raise RaidRoomError("钉点已满", 409)
    if mark_kind == MARK_LINE and _mark_count(db, room.id, MARK_LINE, slug) >= MAX_LINES:
        raise RaidRoomError("直线已满", 409)
    if mark_kind == MARK_STROKE and _mark_count(db, room.id, MARK_STROKE, slug) >= MAX_STROKES:
        raise RaidRoomError("笔画已满", 409)
    if mark_kind == MARK_TEXT and _mark_count(db, room.id, MARK_TEXT, slug) >= MAX_TEXTS:
        raise RaidRoomError("文字已满", 409)
    text = normalize_mark_label(label) if mark_kind == MARK_TEXT else ""
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
        map_slug=slug,
        floor=_floor(floor),
        x=start_x,
        z=start_z,
        x2=end_x,
        z2=end_z,
        points_json=points_json,
        label=text,
        created_at=stamp,
    )
    db.add(row)
    db.flush()
    snapshot = serialize_room(db, room, viewer=user)
    mark = next((item for item in snapshot["marks"] if item["id"] == row.id), None)
    if mark is None:
        mark = serialize_mark(row, _display_name(user))
    return snapshot, mark


def move_text_mark(
    db: Session,
    public_id: str,
    user: User,
    mark_id: int,
    *,
    x: Any,
    z: Any,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    row = (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.id == mark_id, TarkovRaidRoomMark.room_id == room.id)
        .first()
    )
    if row is None or (row.map_slug or "") != slug:
        return serialize_room(db, room, viewer=user), None
    if row.kind != MARK_TEXT:
        raise RaidRoomError("只能移动文字")
    row.x = _coord(x, "x")
    row.z = _coord(z, "z")
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
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    row = (
        db.query(TarkovRaidRoomMark)
        .filter(TarkovRaidRoomMark.id == mark_id, TarkovRaidRoomMark.room_id == room.id)
        .first()
    )
    if row is None or (row.map_slug or "") != slug:
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
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    row = (
        db.query(TarkovRaidRoomMark)
        .filter(
            TarkovRaidRoomMark.room_id == room.id,
            TarkovRaidRoomMark.author_user_id == user.id,
            TarkovRaidRoomMark.map_slug == slug,
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
    room = _get_room(db, public_id)
    _require_active_member(db, room, user, now=now)
    slug = _require_view_map(room.public_id, user.id)
    if room.host_user_id != user.id:
        raise RaidRoomError("只有房主可以清板", 403)
    (
        db.query(TarkovRaidRoomMark)
        .filter(
            TarkovRaidRoomMark.room_id == room.id,
            TarkovRaidRoomMark.map_slug == slug,
        )
        .delete(synchronize_session=False)
    )
    db.flush()
    return serialize_room(db, room, viewer=user)
