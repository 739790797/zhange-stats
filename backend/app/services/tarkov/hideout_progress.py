"""藏身处规划器：默认等级、设施前置、升降级级联。

商人好感 / 技能只展示绿灯，不挡升降级。蓝边（EOD）仓库地板为 4。
"""

from __future__ import annotations

from typing import Any, Mapping

STASH_SLUG = "stash"
STATION_ID_MAX = 64
LEVEL_MAX = 20
STASH_FLOOR_STANDARD = 1
STASH_FLOOR_EOD = 4
EDITION_STANDARD = "standard"
EDITION_EOD = "eod"

ReqStatus = str  # "met" | "unmet" | "unset"


def parse_game_edition(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if text in ("eod", "edge", "blue", EDITION_EOD):
        return EDITION_EOD
    return EDITION_STANDARD


def stash_floor_for_edition(raw: Any) -> int:
    if parse_game_edition(raw) == EDITION_EOD:
        return STASH_FLOOR_EOD
    return STASH_FLOOR_STANDARD


def _stash_floor_value(raw: Any) -> int:
    try:
        floor = int(raw)
    except (TypeError, ValueError):
        return STASH_FLOOR_STANDARD
    return max(floor, STASH_FLOOR_STANDARD)


def default_level(
    station: Mapping[str, Any] | None,
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> int:
    slug = str((station or {}).get("slug") or "").strip().lower()
    if slug == STASH_SLUG:
        high = max(max_level(station), 1)
        return min(_stash_floor_value(stash_floor), high)
    return 0


def max_level(station: Mapping[str, Any] | None) -> int:
    levels = (station or {}).get("levels") or []
    highest = 0
    for row in levels:
        if isinstance(row, dict):
            try:
                highest = max(highest, int(row.get("level") or 0))
            except (TypeError, ValueError):
                continue
    return highest


def clamp_level(
    station: Mapping[str, Any] | None,
    raw: Any,
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> int:
    low = default_level(station, stash_floor=stash_floor)
    high = max(max_level(station), low)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return low
    return min(max(value, low), high)


def index_stations(stations: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in stations or []:
        if not isinstance(row, dict):
            continue
        ident = str(row.get("id") or "").strip()
        if ident:
            out[ident] = row
    return out


def filled_levels(
    stations: list[dict[str, Any]] | None,
    stored: Mapping[str, Any] | None = None,
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> dict[str, int]:
    by_id = index_stations(stations)
    raw = stored if isinstance(stored, Mapping) else {}
    out: dict[str, int] = {}
    for ident, station in by_id.items():
        if ident in raw:
            out[ident] = clamp_level(station, raw[ident], stash_floor=stash_floor)
        else:
            out[ident] = default_level(station, stash_floor=stash_floor)
    return out


def level_spec(station: Mapping[str, Any] | None, level: int) -> dict[str, Any] | None:
    for row in (station or {}).get("levels") or []:
        if not isinstance(row, dict):
            continue
        try:
            if int(row.get("level") or 0) == level:
                return row
        except (TypeError, ValueError):
            continue
    return None


def station_prereqs_met(
    spec: Mapping[str, Any] | None,
    levels: Mapping[str, int],
    by_id: Mapping[str, dict[str, Any]],
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> bool:
    if not spec:
        return True
    for req in spec.get("station_requirements") or []:
        if not isinstance(req, dict):
            continue
        other_id = str(req.get("station_id") or "").strip()
        if not other_id:
            continue
        try:
            need = int(req.get("level") or 0)
        except (TypeError, ValueError):
            need = 0
        have = levels.get(other_id)
        if have is None:
            have = default_level(by_id.get(other_id), stash_floor=stash_floor)
        if int(have) < need:
            return False
    return True


def can_set_level(
    station: Mapping[str, Any] | None,
    target: int,
    levels: Mapping[str, int],
    by_id: Mapping[str, dict[str, Any]],
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> bool:
    if station is None:
        return False
    low = default_level(station, stash_floor=stash_floor)
    high = max_level(station)
    if target < low or target > high:
        return False
    if target == low:
        return True
    spec = level_spec(station, target)
    if spec is None:
        return False
    return station_prereqs_met(spec, levels, by_id, stash_floor=stash_floor)


def _cascade(
    levels: dict[str, int],
    by_id: Mapping[str, dict[str, Any]],
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> dict[str, int]:
    changed = True
    while changed:
        changed = False
        for ident, station in by_id.items():
            current = int(
                levels.get(ident, default_level(station, stash_floor=stash_floor))
            )
            low = default_level(station, stash_floor=stash_floor)
            while current > low:
                spec = level_spec(station, current)
                if spec is not None and station_prereqs_met(
                    spec, levels, by_id, stash_floor=stash_floor
                ):
                    break
                current -= 1
                changed = True
            if levels.get(ident) != current:
                levels[ident] = current
                changed = True
    return levels


def apply_level(
    stations: list[dict[str, Any]] | None,
    stored: Mapping[str, Any] | None,
    station_id: str,
    target: int,
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> dict[str, int]:
    ident = str(station_id or "").strip()
    by_id = index_stations(stations)
    station = by_id.get(ident)
    if station is None:
        raise ValueError("未找到藏身处模块")
    current = filled_levels(stations, stored, stash_floor=stash_floor)
    want = clamp_level(station, target, stash_floor=stash_floor)
    now = int(current.get(ident, default_level(station, stash_floor=stash_floor)))
    if want == now:
        return current
    if want > now:
        if want != now + 1:
            raise ValueError("只能逐级升级")
        if not can_set_level(station, want, current, by_id, stash_floor=stash_floor):
            raise ValueError("升级前置未满足")
        current[ident] = want
        return current
    if want != now - 1:
        raise ValueError("只能逐级降级")
    current[ident] = want
    return _cascade(current, by_id, stash_floor=stash_floor)


def req_status(met: bool | None) -> ReqStatus:
    if met is None:
        return "unset"
    return "met" if met else "unmet"


def station_req_met(
    req: Mapping[str, Any],
    levels: Mapping[str, int],
    by_id: Mapping[str, dict[str, Any]],
    stash_floor: int = STASH_FLOOR_STANDARD,
) -> bool:
    other_id = str(req.get("station_id") or "").strip()
    try:
        need = int(req.get("level") or 0)
    except (TypeError, ValueError):
        need = 0
    have = levels.get(other_id)
    if have is None:
        have = default_level(by_id.get(other_id), stash_floor=stash_floor)
    return int(have) >= need


def trader_req_met(req: Mapping[str, Any], trader_levels: Mapping[str, int] | None) -> bool | None:
    if trader_levels is None:
        return None
    ident = str(req.get("id") or "").strip()
    slug = str(req.get("slug") or "").strip().lower()
    try:
        need = int(req.get("level") or 0)
    except (TypeError, ValueError):
        need = 0
    have = trader_levels.get(ident) if ident else None
    if have is None and slug:
        have = trader_levels.get(slug)
    if have is None and ident:
        have = trader_levels.get(ident.lower())
    if have is None:
        return None
    return int(have) >= need


def skill_req_met(req: Mapping[str, Any], skill_levels: Mapping[str, int] | None) -> bool | None:
    if skill_levels is None:
        return None
    ident = str(req.get("skill_id") or req.get("skill") or "").strip()
    try:
        need = int(req.get("level") or 0)
    except (TypeError, ValueError):
        need = 0
    have = skill_levels.get(ident)
    if have is None:
        return False
    return int(have) >= need


def item_req_met(req: Mapping[str, Any], item_counts: Mapping[str, float] | None) -> bool | None:
    if item_counts is None:
        return None
    ident = str(req.get("id") or "").strip()
    try:
        need = float(req.get("count") or 1)
    except (TypeError, ValueError):
        need = 1.0
    have = item_counts.get(ident)
    if have is None:
        return False
    return float(have) >= need
