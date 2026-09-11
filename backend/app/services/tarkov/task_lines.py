"""任务线索引：互斥失败 vs 祖先分叉无法完成。纯投影，不落表。"""

from __future__ import annotations

from typing import Any

EMPTY_LINE = {
    "line_hint": "",
    "mutex_ids": [],
    "blocked_by": [],
    "prereq_ids": [],
    "prestige_cycle": 0,
}

_MAX_HINT_DEPTH = 16


def _id_of(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("_id") or "").strip()
    if value is None:
        return ""
    return str(value).strip()


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _quest_stem(value: Any) -> str:
    """new-beginning-5 与 new-beginning 同线，用 dump/overlay 自己的 slug，不改名称。"""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    head, sep, tail = text.rpartition("-")
    if sep and tail.isdigit():
        return head
    return text


def _task_name(task_id: str, raw: dict[str, Any], locale: dict[str, Any]) -> str:
    for key in (f"{task_id} name", f"{task_id} Name"):
        val = locale.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and set(text) - set("?？� \t"):
            return text
    name = str(raw.get("name") or "").strip()
    if name and name != task_id and not name.lower().endswith(" name"):
        return name
    return str(raw.get("normalizedName") or task_id).strip() or task_id


def _prestige_level(raw: dict[str, Any]) -> int:
    blob = raw.get("requiredPrestige")
    if blob is None:
        blob = raw.get("required_prestige")
    if isinstance(blob, dict):
        for key in ("prestigeLevel", "prestige_level", "level"):
            if blob.get(key) is not None:
                return _as_int(blob.get(key))
        return 0
    return _as_int(blob)


def _has_required_prestige(raw: dict[str, Any]) -> bool:
    blob = raw.get("requiredPrestige")
    if blob is None:
        blob = raw.get("required_prestige")
    if blob in (None, "", False):
        return False
    if isinstance(blob, dict):
        return any(str(v).strip() for v in blob.values() if v not in (None, "", False))
    return bool(str(blob).strip())


_CN_INT = "一二三四五六七八九十"


def prestige_cycle_hint(required_level: int) -> str:
    """requiredPrestige 是接取门槛；同名线要标的是第几转（门槛 0 → 一转）。"""
    cycle = required_level + 1 if required_level >= 0 else 1
    if 1 <= cycle <= 10:
        return f"{_CN_INT[cycle - 1]}转"
    return f"{cycle}转"


def _requirement_complete(row: dict[str, Any]) -> bool:
    """流程图只认「完成前置」。active / failed 不是先后边。"""
    statuses = [
        str(item).strip().lower()
        for item in (row.get("status") or [])
        if str(item).strip()
    ]
    return (not statuses) or ("complete" in statuses)


def _prereq_ids(raw: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in raw.get("taskRequirements") or []:
        if not isinstance(row, dict):
            continue
        if not _requirement_complete(row):
            continue
        ident = _id_of(row.get("task"))
        if not ident:
            ident = _id_of(row.get("taskId"))
        if not ident or ident in seen:
            continue
        seen.add(ident)
        out.append(ident)
    return out


def _fail_complete_ids(raw: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in raw.get("failConditions") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip() != "taskStatus":
            continue
        statuses = [
            str(item).strip().lower()
            for item in (row.get("status") or [])
            if str(item).strip()
        ]
        if "complete" not in statuses:
            continue
        ident = _id_of(row.get("task"))
        if not ident or ident in seen:
            continue
        seen.add(ident)
        out.append(ident)
    return out


def _trader_slug(raw: dict[str, Any]) -> str:
    trader = raw.get("trader")
    if isinstance(trader, dict):
        slug = str(trader.get("normalizedName") or "").strip()
        if slug:
            return slug
    return _id_of(trader)


def collect_task_line_specs(
    tasks_map: dict[str, dict[str, Any]],
    locale: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    loc = locale if isinstance(locale, dict) else {}
    specs: dict[str, dict[str, Any]] = {}
    for key, raw in tasks_map.items():
        if not isinstance(raw, dict):
            continue
        ident = str(raw.get("id") or key or "").strip()
        if not ident:
            continue
        specs[ident] = {
            "id": ident,
            "name": _task_name(ident, raw, loc),
            "normalized_stem": _quest_stem(raw.get("normalizedName")),
            "trader_slug": _trader_slug(raw),
            "faction_name": str(raw.get("factionName") or raw.get("faction_name") or "Any"),
            "prestige_level": _prestige_level(raw),
            "has_prestige_req": _has_required_prestige(raw),
            "prereq_ids": _prereq_ids(raw),
            "fail_complete_ids": _fail_complete_ids(raw),
        }
    return specs


def _mutex_neighbors(specs: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """直接互斥边对称化。不要做连通分量：共享冲突任务会把平行线误并成一组。"""
    neigh: dict[str, set[str]] = {ident: set() for ident in specs}
    for ident, spec in specs.items():
        for other in spec["fail_complete_ids"]:
            if other not in specs or other == ident:
                continue
            neigh[ident].add(other)
            neigh[other].add(ident)
    return neigh


def _ancestors(task_id: str, specs: dict[str, dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    stack = list(specs.get(task_id, {}).get("prereq_ids") or [])
    while stack:
        cur = stack.pop()
        if not cur or cur == task_id or cur in seen:
            continue
        seen.add(cur)
        stack.extend(specs.get(cur, {}).get("prereq_ids") or [])
    return seen


def _frontier(task_id: str, depth: int, specs: dict[str, dict[str, Any]]) -> set[str]:
    layer = {task_id}
    visited = {task_id}
    for _ in range(depth):
        nxt: set[str] = set()
        for node in layer:
            for prereq in specs.get(node, {}).get("prereq_ids") or []:
                if not prereq or prereq in visited:
                    continue
                visited.add(prereq)
                if prereq in specs:
                    nxt.add(prereq)
        layer = nxt
        if not layer:
            return set()
    return layer


def _cluster_key(spec: dict[str, Any]) -> tuple[str, str]:
    return (str(spec.get("name") or "").strip(), str(spec.get("trader_slug") or "").strip())


def _name_clusters(specs: dict[str, dict[str, Any]]) -> list[list[str]]:
    buckets: dict[tuple[str, str], list[str]] = {}
    for ident, spec in specs.items():
        name, trader = _cluster_key(spec)
        if not name:
            continue
        buckets.setdefault((name, trader), []).append(ident)
    return [ids for ids in buckets.values() if len(ids) >= 2]


def _stem_clusters(specs: dict[str, dict[str, Any]]) -> list[list[str]]:
    buckets: dict[tuple[str, str], list[str]] = {}
    for ident, spec in specs.items():
        stem = str(spec.get("normalized_stem") or "").strip()
        trader = str(spec.get("trader_slug") or "").strip()
        if not stem:
            continue
        buckets.setdefault((stem, trader), []).append(ident)
    return [ids for ids in buckets.values() if len(ids) >= 2]


def _faction_hints(cluster: list[str], specs: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    factions = {
        ident: str(specs[ident].get("faction_name") or "Any").strip() or "Any"
        for ident in cluster
    }
    distinct = {value for value in factions.values() if value != "Any"}
    if len(distinct) < 2:
        return None
    return {ident: value if value != "Any" else "" for ident, value in factions.items()}


def _prestige_hints(cluster: list[str], specs: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    levels = {ident: _as_int(specs[ident].get("prestige_level")) for ident in cluster}
    if len(set(levels.values())) < 2:
        return None
    return {
        ident: prestige_cycle_hint(level)
        for ident, level in levels.items()
    }


def _prestige_cycles(specs: dict[str, dict[str, Any]]) -> dict[str, int]:
    """有 requiredPrestige，或与其同名同商人的转生线，标第几转（1 起）。"""
    gated = {
        ident
        for ident, spec in specs.items()
        if _as_int(spec.get("prestige_level")) > 0 or spec.get("has_prestige_req")
    }
    family = set(gated)
    for cluster in (*_name_clusters(specs), *_stem_clusters(specs)):
        if any(ident in gated for ident in cluster):
            family.update(cluster)
    return {
        ident: (_as_int(specs[ident].get("prestige_level")) + 1) if ident in family else 0
        for ident in specs
    }


def _prereq_hints(cluster: list[str], specs: dict[str, dict[str, Any]]) -> dict[str, str]:
    empty = {ident: "" for ident in cluster}
    for depth in range(1, _MAX_HINT_DEPTH + 1):
        name_sets: dict[str, set[str]] = {}
        for ident in cluster:
            names = {
                str(specs[node]["name"]).strip()
                for node in _frontier(ident, depth, specs)
                if node in specs and str(specs[node].get("name") or "").strip()
            }
            name_sets[ident] = names
        if not any(name_sets.values()):
            return empty
        shared = set.intersection(*name_sets.values()) if name_sets else set()
        unique = {ident: names - shared for ident, names in name_sets.items()}
        unique_union = set()
        for names in unique.values():
            unique_union |= names
        if not unique_union:
            continue
        if len(unique_union) == 1:
            continue
        return {
            ident: f"经「{sorted(names)[0]}」" if names else ""
            for ident, names in unique.items()
        }
    return empty


def _line_hints(specs: dict[str, dict[str, Any]]) -> dict[str, str]:
    hints = {ident: "" for ident in specs}
    for cluster in _name_clusters(specs):
        faction = _faction_hints(cluster, specs)
        if faction is not None:
            hints.update(faction)
            continue
        prestige = _prestige_hints(cluster, specs)
        if prestige is not None:
            hints.update(prestige)
            continue
        hints.update(_prereq_hints(cluster, specs))
    for cluster in _stem_clusters(specs):
        prestige = _prestige_hints(cluster, specs)
        if prestige is None:
            continue
        for ident, hint in prestige.items():
            if not hints.get(ident):
                hints[ident] = hint
    return hints


def build_task_line_index(specs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """specs[id] → {line_hint, mutex_ids, blocked_by, prereq_ids, prestige_cycle}。"""
    if not specs:
        return {}
    neigh = _mutex_neighbors(specs)
    hints = _line_hints(specs)
    cycles = _prestige_cycles(specs)
    out: dict[str, dict[str, Any]] = {}
    for ident in specs:
        mutex_ids = sorted(neigh.get(ident) or ())
        blocked: set[str] = set()
        ancs = _ancestors(ident, specs)
        for anc in ancs:
            for peer in neigh.get(anc) or ():
                if peer not in ancs:
                    blocked.add(peer)
        out[ident] = {
            "line_hint": hints.get(ident) or "",
            "mutex_ids": mutex_ids,
            "blocked_by": sorted(blocked),
            "prereq_ids": list(specs[ident].get("prereq_ids") or []),
            "prestige_cycle": int(cycles.get(ident) or 0),
        }
    return out


def index_task_lines(
    tasks_map: dict[str, dict[str, Any]],
    locale: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    return build_task_line_index(collect_task_line_specs(tasks_map, locale))


def stamp_task_line_fields(
    row: dict[str, Any],
    index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ident = str(row.get("id") or "").strip()
    meta = index.get(ident) or EMPTY_LINE
    row["line_hint"] = str(meta.get("line_hint") or "")
    row["mutex_ids"] = list(meta.get("mutex_ids") or [])
    row["blocked_by"] = list(meta.get("blocked_by") or [])
    row["prereq_ids"] = list(meta.get("prereq_ids") or [])
    row["prestige_cycle"] = int(meta.get("prestige_cycle") or 0)
    return row
