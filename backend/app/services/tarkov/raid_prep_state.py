"""联机大厅单人准备：按账号 / 模式 / 地图保存勾选、目标完成和钥匙声明。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserRaidPrep
from app.models.user import User
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode
from app.services.tarkov.raid_rooms import normalize_room_map_slug

SELECTED_MAX = 40
ID_MAX = 64
OBJECTIVE_MAX = 200
KEY_BRING_MAX = 80


class TarkovRaidPrepStateError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def _map_slug(raw: str) -> str:
    slug = normalize_room_map_slug(raw)
    if not slug:
        raise TarkovRaidPrepStateError("地图无效")
    return slug


def _clip_id(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text or len(text) > ID_MAX:
        return ""
    return text


def _id_list(raw: Any, *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if not isinstance(raw, list):
        return out
    for item in raw:
        ident = _clip_id(item)
        if not ident or ident in seen:
            continue
        seen.add(ident)
        out.append(ident)
        if len(out) >= limit:
            break
    return out


def _objective_pairs(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        task_id = _clip_id(item.get("task_id"))
        objective_id = _clip_id(item.get("objective_id"))
        if not task_id or not objective_id:
            continue
        key = (task_id, objective_id)
        if key in seen:
            continue
        seen.add(key)
        out.append({"task_id": task_id, "objective_id": objective_id})
        if len(out) >= OBJECTIVE_MAX:
            break
    return out


def _empty_state(map_slug: str, game_mode: str) -> dict[str, Any]:
    return {
        "map": map_slug,
        "game_mode": game_mode,
        "selected": [],
        "objective_dones": [],
        "key_brings": [],
        "updated_at": None,
    }


def serialize_state(row: TarkovUserRaidPrep) -> dict[str, Any]:
    return {
        "map": row.map_slug,
        "game_mode": parse_game_mode(row.game_mode),
        "selected": _id_list(row.selected_json, limit=SELECTED_MAX),
        "objective_dones": _objective_pairs(row.objective_dones_json),
        "key_brings": _id_list(row.key_brings_json, limit=KEY_BRING_MAX),
        "updated_at": row.updated_at.isoformat(timespec="seconds")
        if row.updated_at
        else None,
    }


def get_state(
    db: Session,
    user: User,
    map_slug: str,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    slug = _map_slug(map_slug)
    mode = _mode(game_mode)
    row = (
        db.query(TarkovUserRaidPrep)
        .filter(
            TarkovUserRaidPrep.user_id == user.id,
            TarkovUserRaidPrep.game_mode == mode,
            TarkovUserRaidPrep.map_slug == slug,
        )
        .one_or_none()
    )
    if row is None:
        return _empty_state(slug, mode)
    return serialize_state(row)


def put_state(
    db: Session,
    user: User,
    map_slug: str,
    *,
    selected: Any = None,
    objective_dones: Any = None,
    key_brings: Any = None,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    slug = _map_slug(map_slug)
    mode = _mode(game_mode)
    stamp = now or now_naive()
    selected_ids = _id_list(selected, limit=SELECTED_MAX)
    dones = _objective_pairs(objective_dones)
    brings = _id_list(key_brings, limit=KEY_BRING_MAX)
    row = (
        db.query(TarkovUserRaidPrep)
        .filter(
            TarkovUserRaidPrep.user_id == user.id,
            TarkovUserRaidPrep.game_mode == mode,
            TarkovUserRaidPrep.map_slug == slug,
        )
        .one_or_none()
    )
    if row is None:
        row = TarkovUserRaidPrep(
            user_id=user.id,
            game_mode=mode,
            map_slug=slug,
            selected_json=selected_ids,
            objective_dones_json=dones,
            key_brings_json=brings,
            updated_at=stamp,
        )
        db.add(row)
    else:
        row.selected_json = selected_ids
        row.objective_dones_json = dones
        row.key_brings_json = brings
        row.updated_at = stamp
    db.flush()
    return serialize_state(row)
