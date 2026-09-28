"""塔科夫地图筛选喜好：一个账号一份，网页和 App 读写同一份。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovUserMapFilter
from app.models.user import User

EXTRACT_KINDS = ("pmc", "scav", "shared", "transit")
SPAWN_KINDS = ("pmc", "scav", "sniper", "boss")
GROUP_IDS = frozenset(
    {
        "style",
        "levels",
        "landmarks",
        "extracts",
        "spawns",
        "usable",
        "hazards",
        "lootable",
        "lootLoose",
        "tasks",
        "screenshot",
    }
)
MAX_PREFS_CHARS = 65_536
MAX_MAPS = 40
MAX_KINDS = 80
MAX_KEY = 64


class TarkovMapFiltersError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _bool(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > MAX_KEY:
        return ""
    return text


def _kind_flags(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, bool] = {}
    for key, value in raw.items():
        name = _text(key)
        if not name or not isinstance(value, bool):
            continue
        out[name] = value
        if len(out) >= MAX_KINDS:
            break
    return out


def _named_flags(raw: Any, names: tuple[str, ...]) -> dict[str, bool]:
    row = raw if isinstance(raw, dict) else {}
    return {name: _bool(row.get(name), True) for name in names}


def _floors(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        name = _text(key)
        if not name or not isinstance(value, str):
            continue
        floor = value.strip()
        if len(floor) > MAX_KEY:
            continue
        out[name] = floor
        if len(out) >= MAX_MAPS:
            break
    return out


def _collapsed(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, bool] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if name not in GROUP_IDS or value is not True:
            continue
        out[name] = True
    return out


def normalize_map_filters(raw: Any) -> dict[str, Any]:
    """缺字段时与网页 TarkovMapViewerPrefs 的默认值对齐。"""
    row = raw if isinstance(raw, dict) else {}
    prefs = {
        "style": "svg" if row.get("style") != "tile" else "tile",
        "filterPanelOpen": _bool(row.get("filterPanelOpen"), True),
        "filterGroupsCollapsed": _collapsed(row.get("filterGroupsCollapsed")),
        "floorsByMap": _floors(row.get("floorsByMap")),
        "extractKinds": _named_flags(row.get("extractKinds"), EXTRACT_KINDS),
        "spawnKinds": _named_flags(row.get("spawnKinds"), SPAWN_KINDS),
        "showLabels": _bool(row.get("showLabels"), True),
        "showQuests": _bool(row.get("showQuests"), True),
        "showLocks": _bool(row.get("showLocks"), True),
        "showHazards": _bool(row.get("showHazards"), True),
        "showSwitches": _bool(row.get("showSwitches"), True),
        "showStationary": _bool(row.get("showStationary"), True),
        "showBtrStops": _bool(row.get("showBtrStops"), True),
        "showLootContainers": _bool(row.get("showLootContainers"), False),
        "showLootLoose": _bool(row.get("showLootLoose"), False),
        "hazardKinds": _kind_flags(row.get("hazardKinds")),
        "lootContainerKinds": _kind_flags(row.get("lootContainerKinds")),
        "lootLooseKinds": _kind_flags(row.get("lootLooseKinds")),
    }
    packed = json.dumps(prefs, ensure_ascii=False, separators=(",", ":"))
    if len(packed) > MAX_PREFS_CHARS:
        raise TarkovMapFiltersError("筛选记录过大")
    return prefs


def _stamp(row: TarkovUserMapFilter) -> str | None:
    updated = row.updated_at
    if updated is None:
        return None
    return updated.isoformat()


def get_map_filters(db: Session, user_id: int) -> dict[str, Any]:
    row = db.get(TarkovUserMapFilter, user_id)
    if row is None:
        return {"saved": False, "prefs": None, "updated_at": None}
    return {
        "saved": True,
        "prefs": normalize_map_filters(row.prefs),
        "updated_at": _stamp(row),
    }


def save_map_filters(db: Session, user: User, raw: Any) -> dict[str, Any]:
    prefs = normalize_map_filters(raw)
    row = db.get(TarkovUserMapFilter, user.id)
    if row is None:
        row = TarkovUserMapFilter(user_id=user.id, prefs=prefs, updated_at=now_naive())
        db.add(row)
    else:
        row.prefs = prefs
        row.updated_at = now_naive()
    db.flush()
    return {"saved": True, "prefs": prefs, "updated_at": _stamp(row)}
