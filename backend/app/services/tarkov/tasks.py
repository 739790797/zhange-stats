"""逃离塔科夫任务：json.tarkov.dev tasks dump → 列表/详情投影。

失败不覆盖已有成功 raw。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovTasksRaw
from app.services.tarkov.ammo import SOURCE_JSON_API
from app.services.tarkov.game_mode import (
    GAME_MODES,
    current_game_mode,
    game_mode_scope,
    json_api_prefix,
    json_resource_url,
    parse_game_mode,
    run_for_modes,
)
from app.services.tarkov.overlay import parsed_cache_key
from app.services.tarkov.http import download_bytes

logger = logging.getLogger(__name__)

TASKS_JOB_KEY = "tarkov_tasks_sync"
TASKS_PAGE_SIZE_DEFAULT = 50
TASKS_PAGE_SIZE_MAX = 100
TASKS_LAYOUT_TABLE = "table"
TASKS_LAYOUT_ALL = "all"
DOWNLOAD_TIMEOUT = 180

TARKOV_JSON_TASKS_URL = "https://json.tarkov.dev/regular/tasks"
TARKOV_JSON_TASKS_LOCALE_URL = "https://json.tarkov.dev/regular/tasks_{lang}"


# BSG 商人 id → slug / 英文名（社区简称）
TRADER_BY_ID: dict[str, tuple[str, str]] = {
    "54cb50c76803fa8b248b4571": ("prapor", "Prapor（俄商）"),
    "54cb57776803fa99248b456e": ("therapist", "Therapist（大妈）"),
    "579dc571d53a0658a154fbec": ("fence", "Fence（黑商）"),
    "58330581ace78e27b8b10cee": ("skier", "Skier（走私客）"),
    "5935c25fb3acc3127c3d8cd9": ("peacekeeper", "Peacekeeper（美商）"),
    "5a7c2eca46aef81a7ca2145d": ("mechanic", "Mechanic（机械师）"),
    "5ac3b934156ae10c4430e83c": ("ragman", "Ragman（服装商）"),
    "5c0647fdd443bc2504c2d371": ("jaeger", "Jaeger（耶格）"),
    "638f541a29ffd1183d187f57": ("lightkeeper", "Lightkeeper（灯塔商人）"),
    "6617beeaa9cfa777ca915b7c": ("ref", "Ref（竞技场裁判）"),
    "656f0f98d80a697f855d34b1": ("btr-driver", "BTR Driver（BTR）"),
}

# 突袭图 id → slug / 中文名（与首页地图格对齐）。
# BSG location MongoID：Streets=TarkovStreets，Ground Zero=Sandbox / Sandbox 21+。
MAP_BY_ID: dict[str, tuple[str, str]] = {
    "55f2d3fd4bdc2d5f408b4567": ("factory", "工厂"),
    "59fc81d786f774390775787e": ("factory-night", "夜间工厂"),
    "56f40101d2720b2a4d8b45d6": ("customs", "海关"),
    "5704e3c2d2720bac5b8b4567": ("woods", "森林"),
    "5704e554d2720bac5b8b456e": ("shoreline", "海岸线"),
    "5714dbc024597771384a510d": ("interchange", "立交桥"),
    "5704e5fad2720bc05b8b4567": ("reserve", "储备站"),
    "5704e4dad2720bb55b8b4567": ("lighthouse", "灯塔"),
    "5b0fc42d86f7744a585f9105": ("the-lab", "实验室"),
    "5714dc692459777137212e12": ("streets", "塔科夫街区"),
    "653e6760052c01c1c805532f": ("ground-zero", "中心区"),
    "65b8d6f5cdde2479cb2a3125": ("ground-zero", "中心区"),
    "6733700029c367a3d40b02af": ("labyrinth", "迷宫"),
    "69af492a4819ea4ba10a69c5": ("icebreaker", "破冰船"),
    "65cc8f81a9aac3e77d0cfd3e": ("terminal", "码头"),
    "68236e8153654e8c1200798a": ("ground-zero", "中心区"),
}

# 首页短 id / json.tarkov.dev normalizedName / 任务 map_slug 互认
MAP_SLUG_EQUIV_GROUPS: tuple[tuple[str, ...], ...] = (
    ("streets", "streets-of-tarkov"),
    ("lab", "the-lab"),
    ("labyrinth", "the-labyrinth"),
    ("night-factory", "factory-night"),
    ("ground-zero", "ground-zero-21", "ground-zero-tutorial"),
    ("customs", "bigmap"),
)

_parsed_lock = threading.Lock()
_parsed_cache: tuple[str, list[dict[str, Any]], dict[str, Any]] | None = None
# cache_key:canon_map → (map_name, rows)；与 _parsed_cache 同锁、同次 sync 清空
_raid_prep_cache: dict[str, tuple[str, list[dict[str, Any]]]] = {}
# cache_key → map_slug → {task_id: name}
_raid_prep_index_cache: dict[str, dict[str, dict[str, dict[str, str]]]] = {}


class TarkovTasksError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class TasksUpstreamBundle:
    source: str
    payload: dict[str, Any]
    note: str


def _http_request(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DOWNLOAD_TIMEOUT,
) -> bytes:
    return download_bytes(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
        error_cls=TarkovTasksError,
    )


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_match_keys(map_slug: str) -> tuple[set[str], set[str]]:
    """选中地图 → 可匹配的 slug 集合 + 地图 id 集合。"""
    key = (map_slug or "").strip().lower()
    if not key:
        return set(), set()
    keys = {key}
    for group in MAP_SLUG_EQUIV_GROUPS:
        if key in group:
            keys.update(group)
            break
    ids = {mid for mid, (slug, _name) in MAP_BY_ID.items() if slug in keys}
    return keys, ids


def _norm_map_label(text: str) -> str:
    return re.sub(r"[\s_]+", "-", (text or "").strip().lower())


def _map_labels(keys: set[str], ids: set[str]) -> set[str]:
    labels: set[str] = set()
    for mid, (slug, name) in MAP_BY_ID.items():
        if slug not in keys and mid not in ids:
            continue
        text = _norm_map_label(name)
        if text:
            labels.add(text)
    return labels


def _map_ref_hits(
    ref: dict[str, Any] | None,
    keys: set[str],
    ids: set[str],
    labels: set[str] | None = None,
) -> bool:
    if not isinstance(ref, dict):
        return False
    slug = _norm_map_label(str(ref.get("slug") or ref.get("map_slug") or ""))
    if slug and slug in keys:
        return True
    map_id = str(ref.get("map_id") or "").strip()
    if map_id:
        return map_id in ids
    ident = str(ref.get("id") or "").strip()
    if ident and ident in ids:
        return True
    name = _norm_map_label(str(ref.get("name") or ref.get("map_name") or ""))
    if not name:
        return False
    if name in keys:
        return True
    hit_labels = labels if labels is not None else _map_labels(keys, ids)
    return name in hit_labels


def task_hits_map(detail: dict[str, Any], map_slug: str) -> bool:
    keys, ids = map_match_keys(map_slug)
    if not keys and not ids:
        return False
    if str(detail.get("map_id") or "").strip() in ids:
        return True
    if _norm_map_label(str(detail.get("map_slug") or "")) in keys:
        return True
    labels = _map_labels(keys, ids)
    name = _norm_map_label(str(detail.get("map_name") or ""))
    if name and (name in keys or name in labels):
        return True
    for obj in detail.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        for row in obj.get("maps") or []:
            if _map_ref_hits(row, keys, ids, labels):
                return True
        for zone in obj.get("zones") or []:
            if _map_ref_hits(zone, keys, ids, labels):
                return True
        for loc in obj.get("possible_locations") or []:
            if _map_ref_hits(loc, keys, ids, labels):
                return True
    return False


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _id_of(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("_id") or "").strip()
    if value is None:
        return ""
    return str(value).strip()


_GARBLED_NAME_RE = re.compile(r"^[?？�\s]+$")


def _is_garbled_name(name: str) -> bool:
    """BSG / tarkov.dev 中文 locale 缺译时常写成 ????，不能当名称。"""
    n = (name or "").strip()
    return bool(n) and _GARBLED_NAME_RE.fullmatch(n) is not None


def _locale_lookup(locale: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if not key:
            continue
        val = locale.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and not _is_garbled_name(text):
            return text
    return ""


def _is_placeholder_name(task_id: str, name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    if _is_garbled_name(n):
        return True
    ident = (task_id or "").strip()
    if ident and n == ident:
        return True
    if ident and ident in n and n.lower().endswith(" name"):
        return True
    return False


def trader_info(trader_id: str, raw: Any = None) -> tuple[str, str]:
    tid = (trader_id or "").strip()
    if tid in TRADER_BY_ID:
        return TRADER_BY_ID[tid]
    if isinstance(raw, dict):
        slug = str(raw.get("normalizedName") or "").strip()
        name = str(raw.get("name") or "").strip()
        if slug or name:
            return slug or tid, name or slug or tid
    return tid, tid


def map_info(map_id: str, raw: Any = None) -> tuple[str, str]:
    mid = (map_id or "").strip()
    if mid in MAP_BY_ID:
        return MAP_BY_ID[mid]
    if isinstance(raw, dict):
        slug = str(raw.get("normalizedName") or "").strip()
        name = str(raw.get("name") or "").strip()
        if slug or name:
            return slug or mid, name or slug or mid
    return mid, mid


def _list_to_task_map(rows: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ident = str(raw.get("id") or "").strip()
        if ident:
            out[ident] = raw
    return out


def _tasks_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nested = payload.get("tasks")
    if isinstance(nested, dict):
        return {str(k): v for k, v in nested.items() if isinstance(v, dict)}
    if isinstance(nested, list):
        return _list_to_task_map(nested)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if isinstance(tasks, dict):
        return {str(k): v for k, v in tasks.items() if isinstance(v, dict)}
    if isinstance(tasks, list):
        return _list_to_task_map(tasks)
    return {}


def _locale_map(payload: dict[str, Any]) -> dict[str, Any]:
    locale = payload.get("locale")
    if isinstance(locale, dict):
        return locale
    return {}


def _quest_items_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("questItems")
    if not isinstance(raw, (dict, list)):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        raw = data.get("questItems") if isinstance(data, dict) else None
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for row in raw:
            if not isinstance(row, dict):
                continue
            ident = str(row.get("id") or "").strip()
            if ident:
                out[ident] = row
        return out
    return {}


_EXP_BONUS_RE = re.compile(r"(?i)^ExpBonus(.+)$")
_EXIT_SPLIT_RE = re.compile(r"[&,|/]+")
_EXIT_STATUS_CANON = {
    "survived": "Survived",
    "runner": "Runner",
    "runthrough": "Runner",
    "missinginaction": "MissingInAction",
    "mia": "MissingInAction",
    "killed": "Killed",
    "kia": "Killed",
    "left": "Left",
    "transit": "Transit",
}


def canonicalize_exit_status(token: str) -> str | None:
    raw = (token or "").strip()
    if not raw:
        return None
    match = _EXP_BONUS_RE.match(raw)
    if match:
        raw = match.group(1)
    key = raw.replace(" ", "").replace("_", "").replace("-", "").lower()
    return _EXIT_STATUS_CANON.get(key)


def normalize_objective_exit(obj: dict[str, Any]) -> tuple[list[str], str]:
    """对齐 tarkov.dev：exitStatus 译成撤离状态；ExpBonus* 不是撤离点名。"""
    seen: list[str] = []

    def add(status: str | None) -> None:
        if status and status not in seen:
            seen.append(status)

    for raw in obj.get("exitStatus") or []:
        token = str(raw).strip()
        if not token:
            continue
        add(canonicalize_exit_status(token) or token)

    leftover: list[str] = []
    for part in _EXIT_SPLIT_RE.split(str(obj.get("exitName") or "")):
        token = part.strip()
        if not token:
            continue
        canon = canonicalize_exit_status(token)
        if canon:
            add(canon)
        else:
            leftover.append(token)
    exit_name = leftover[0] if leftover else ""
    if "ExpBonus" in exit_name:
        exit_name = ""
    return seen, exit_name


def download_json_api_tasks(*, lang: str = "zh") -> TasksUpstreamBundle:
    raw = _http_request(json_resource_url("tasks"), timeout=90)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovTasksError("json.tarkov.dev tasks 解析失败") from exc
    if not isinstance(payload, dict) or not _tasks_map(payload):
        raise TarkovTasksError("json.tarkov.dev 未解析到任务")

    try:
        loc_raw = _http_request(
            json_resource_url("tasks", lang=lang),
            timeout=60,
        )
        loc_payload = json.loads(loc_raw.decode("utf-8"))
        loc_data = loc_payload.get("data") if isinstance(loc_payload, dict) else None
        if isinstance(loc_data, dict) and loc_data:
            payload = dict(payload)
            payload["locale"] = loc_data
    except TarkovTasksError:
        logger.warning("json.tarkov.dev tasks_%s locale unavailable", lang)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("json.tarkov.dev tasks_%s locale parse failed", lang)

    return TasksUpstreamBundle(
        source=SOURCE_JSON_API,
        payload=payload,
        note=f"json.tarkov.dev/{json_api_prefix()}/tasks",
    )


def project_task_summary(
    raw: dict[str, Any],
    locale: dict[str, Any],
) -> dict[str, Any] | None:
    task_id = str(raw.get("id") or "").strip()
    if not task_id:
        return None
    name = str(raw.get("name") or "")
    loc_name = _locale_lookup(locale, f"{task_id} name", f"{task_id} Name")
    if loc_name:
        name = loc_name
    elif _is_placeholder_name(task_id, name):
        name = str(raw.get("normalizedName") or task_id)

    trader_raw = raw.get("trader")
    trader_id = _id_of(trader_raw)
    trader_slug, trader_name = trader_info(trader_id, trader_raw)

    map_raw = raw.get("map")
    map_id = _id_of(map_raw)
    map_slug, map_name = ("", "")
    if map_id:
        map_slug, map_name = map_info(map_id, map_raw)

    objectives = raw.get("objectives") if isinstance(raw.get("objectives"), list) else []
    return {
        "id": task_id,
        "name": name,
        "normalized_name": str(raw.get("normalizedName") or ""),
        "trader_id": trader_id,
        "trader_slug": trader_slug,
        "trader_name": trader_name,
        "map_id": map_id,
        "map_slug": map_slug,
        "map_name": map_name,
        "min_player_level": _as_int(raw.get("minPlayerLevel")),
        "min_trader_level": task_min_trader_level(raw, trader_id),
        "experience": _as_int(raw.get("experience")),
        "lightkeeper_required": _as_bool(raw.get("lightkeeperRequired")),
        "kappa_required": _as_bool(raw.get("kappaRequired")),
        "faction_name": str(raw.get("factionName") or "Any"),
        "task_image_link": str(raw.get("taskImageLink") or ""),
        "wiki_link": str(raw.get("wikiLink") or ""),
        "objective_count": len(objectives),
        "objective_types": unique_objective_types(objectives),
    }


def unique_objective_types(objectives: list[Any]) -> list[str]:
    """目标 type 去重，保游戏内出现顺序。"""
    out: list[str] = []
    seen: set[str] = set()
    for obj in objectives:
        if not isinstance(obj, dict):
            continue
        typ = str(obj.get("type") or "").strip()
        if not typ or typ in seen:
            continue
        seen.add(typ)
        out.append(typ)
    return out


def _resolve_obj_description(
    obj: dict[str, Any],
    locale: dict[str, Any],
) -> str:
    oid = str(obj.get("id") or "").strip()
    desc = str(obj.get("description") or "").strip()
    loc = _locale_lookup(locale, oid, f"{oid} description", f"{oid} Description")
    if loc:
        return loc
    if oid and desc == oid:
        return desc
    return desc or oid


def _named_ref(
    value: Any,
    locale: dict[str, Any],
    *,
    kind: str,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ident = _id_of(value)
    name = ""
    slug = ""
    icon = ""
    types: list[str] = []
    if isinstance(value, dict):
        name = str(value.get("name") or "").strip()
        slug = str(value.get("normalizedName") or "").strip()
        icon = str(
            value.get("iconLink")
            or value.get("icon_link")
            or value.get("baseImageLink")
            or ""
        ).strip()
        raw_types = value.get("types")
        if isinstance(raw_types, list):
            types = [str(t) for t in raw_types if t is not None and str(t).strip()]
    if kind == "map" and ident:
        slug2, name2 = map_info(ident, value if isinstance(value, dict) else None)
        slug = slug2 or slug
        if not name or _is_placeholder_name(ident, name):
            name = name2
    if kind == "trader" and ident:
        slug2, name2 = trader_info(ident, value if isinstance(value, dict) else None)
        slug = slug or slug2
        if not name or _is_placeholder_name(ident, name):
            name = name2
    if kind == "task" and ident:
        loc = _locale_lookup(locale, f"{ident} name", f"{ident} Name")
        if loc:
            name = loc
        elif not name or _is_placeholder_name(ident, name):
            name = str(value.get("normalizedName") if isinstance(value, dict) else "") or ident
    if kind == "item" and ident:
        loc = _locale_lookup(locale, f"{ident} Name", f"{ident} name")
        if loc:
            name = loc
        elif not name or _is_placeholder_name(ident, name):
            qi = (quest_items or {}).get(ident)
            if isinstance(qi, dict):
                qname = str(qi.get("name") or "").strip()
                if qname and not _is_placeholder_name(ident, qname):
                    name = qname
                if not icon:
                    icon = str(
                        qi.get("iconLink")
                        or qi.get("icon_link")
                        or qi.get("baseImageLink")
                        or ""
                    ).strip()
    return {
        "id": ident,
        "slug": slug,
        "name": name or ident,
        "icon_link": icon,
        "types": types,
    }


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _named_refs(
    values: Any,
    locale: dict[str, Any],
    *,
    kind: str,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if isinstance(values, dict):
        rows = list(values.values())
    elif isinstance(values, list):
        rows = values
    else:
        rows = [values] if values not in (None, "") else []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not _id_of(raw) and not (
            isinstance(raw, dict) and str(raw.get("name") or "").strip()
        ):
            continue
        ref = _named_ref(raw, locale, kind=kind, quest_items=quest_items)
        ident = str(ref.get("id") or ref.get("name") or "").strip()
        if not ident or ident in seen:
            continue
        seen.add(ident)
        out.append(ref)
    return out


def _named_ref_groups(
    raw: Any,
    locale: dict[str, Any],
    *,
    kind: str,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> list[list[dict[str, Any]]]:
    if not isinstance(raw, list) or not raw:
        return []
    groups: list[list[dict[str, Any]]] = []
    for group in raw:
        items = group if isinstance(group, list) else [group]
        refs = _named_refs(items, locale, kind=kind, quest_items=quest_items)
        if refs:
            groups.append(refs)
    return groups


def _project_number_compare(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        method = str(raw.get("compareMethod") or raw.get("compare_method") or "").strip()
        if "value" not in raw and "level" not in raw:
            if not method:
                return None
        value = raw.get("value")
        if value is None:
            value = raw.get("level")
        if value is None or value == "":
            return {"compare_method": method, "value": None}
        return {"compare_method": method, "value": _as_number(value)}
    if raw is None or raw == "":
        return None
    return {"compare_method": "", "value": _as_number(raw)}


def _project_health_effect(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    body_parts = [
        str(part).strip()
        for part in (raw.get("bodyParts") or raw.get("body_parts") or [])
        if str(part).strip()
    ]
    effects = [
        str(item).strip()
        for item in (raw.get("effects") or [])
        if str(item).strip()
    ]
    time = _project_number_compare(raw.get("time"))
    if not body_parts and not effects and time is None:
        return None
    return {"body_parts": body_parts, "effects": effects, "time": time}


def _project_attributes(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        req = row.get("requirement") if isinstance(row.get("requirement"), dict) else row
        cmp = _project_number_compare(req)
        if not name and cmp is None:
            continue
        out.append(
            {
                "name": name,
                "compare_method": "" if cmp is None else str(cmp.get("compare_method") or ""),
                "value": None if cmp is None else cmp.get("value"),
            }
        )
    return out


def _project_skill(raw: Any) -> tuple[str, int | None]:
    if isinstance(raw, dict):
        name = str(raw.get("name") or raw.get("skill") or "").strip()
        level = raw.get("level")
        if level is None:
            level = raw.get("value")
        return name, _opt_int(level)
    if raw is None or raw == "":
        return "", None
    return str(raw).strip(), None


def _project_image_ref(raw: Any, locale: dict[str, Any]) -> dict[str, Any] | None:
    ident = _id_of(raw)
    name = ""
    slug = ""
    icon = ""
    extra_type = ""
    if isinstance(raw, dict):
        name = str(raw.get("name") or "").strip()
        slug = str(raw.get("normalizedName") or "").strip()
        icon = str(
            raw.get("imageLink")
            or raw.get("iconLink")
            or raw.get("icon_link")
            or raw.get("image_link")
            or ""
        ).strip()
        extra_type = str(
            raw.get("customizationType") or raw.get("customization_type") or ""
        ).strip()
        if ident:
            loc = _locale_lookup(locale, f"{ident} name", f"{ident} Name", ident)
            if loc:
                name = loc
    elif raw not in (None, ""):
        ident = str(raw).strip()
    if not ident and not name:
        return None
    return {
        "id": ident,
        "slug": slug,
        "name": name or ident,
        "image_link": icon,
        "customization_type": extra_type,
    }


def _empty_rewards() -> dict[str, Any]:
    return {
        "items": [],
        "trader_standing": [],
        "offer_unlock": [],
        "skill_level_reward": [],
        "trader_unlock": [],
        "craft_unlock": [],
        "achievement": [],
        "customization": [],
    }


def _craft_reward_item(row: dict[str, Any]) -> Any:
    product = row.get("productItem") or row.get("rewardItem") or row.get("item")
    if product not in (None, ""):
        return product
    rewards = row.get("rewardItems") or row.get("rewards")
    if isinstance(rewards, list) and rewards:
        first = rewards[0]
        if isinstance(first, dict):
            return first.get("item") if first.get("item") not in (None, "") else first
        return first
    return None


def _project_offer_unlock(
    row: Any,
    locale: dict[str, Any],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    item_raw = row.get("item")
    item = _named_ref(
        item_raw.get("item") if isinstance(item_raw, dict) and item_raw.get("item") else item_raw,
        locale,
        kind="item",
        quest_items=quest_items,
    )
    trader = _named_ref(row.get("trader"), locale, kind="trader")
    ident = str(row.get("id") or item.get("id") or "").strip()
    if not ident and not trader["id"] and not item["id"]:
        return None
    return {
        "id": ident,
        "trader": trader if trader["id"] or trader["slug"] else None,
        "level": _as_int(row.get("level")),
        "item": item if item["id"] else None,
    }


def _project_craft_unlock(
    row: Any,
    locale: dict[str, Any],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if isinstance(row, dict):
        ident = str(row.get("id") or "").strip()
        station = _named_ref(row.get("station"), locale, kind="station")
        item_raw = _craft_reward_item(row)
        item = (
            _named_ref(item_raw, locale, kind="item", quest_items=quest_items)
            if item_raw not in (None, "")
            else None
        )
        if item is not None and not item.get("id"):
            item = None
        if not ident and not station.get("id") and item is None:
            return None
        return {
            "id": ident,
            "station": station if station.get("id") or station.get("slug") else None,
            "level": _as_int(row.get("level")),
            "item": item,
        }
    ident = _id_of(row)
    if not ident:
        return None
    return {"id": ident, "station": None, "level": 0, "item": None}


def _project_prestige(raw: Any, locale: dict[str, Any]) -> dict[str, Any] | None:
    if raw in (None, "", False):
        return None
    if isinstance(raw, dict):
        ident = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        if ident:
            loc = _locale_lookup(locale, f"{ident} name", f"{ident} Name")
            if loc:
                name = loc
        level = raw.get("prestigeLevel")
        if level is None:
            level = raw.get("prestige_level")
        if level is None:
            level = raw.get("level")
        icon = str(raw.get("imageLink") or raw.get("iconLink") or raw.get("image_link") or "").strip()
        if not ident and not name and level is None:
            return None
        return {
            "id": ident,
            "name": name or ident,
            "prestige_level": _as_int(level),
            "image_link": icon,
        }
    level = _opt_int(raw)
    if level is None:
        ident = str(raw).strip()
        if not ident:
            return None
        return {"id": ident, "name": ident, "prestige_level": 0, "image_link": ""}
    if level <= 0:
        return None
    return {"id": "", "name": "", "prestige_level": level, "image_link": ""}


def _objective_item_values(
    obj: dict[str, Any],
    quest_items: dict[str, dict[str, Any]],
) -> list[Any]:
    values: list[Any] = []
    items_raw = obj.get("items")
    if isinstance(items_raw, list):
        values.extend(items_raw)
    elif isinstance(items_raw, dict):
        values.extend(items_raw.values())
    item = obj.get("item")
    if item is not None and item != "":
        values.append(item)
    for key in ("questItem", "markerItem"):
        raw = obj.get(key)
        if raw is None or raw == "":
            continue
        if isinstance(raw, str) and raw in quest_items:
            values.append(quest_items[raw])
        else:
            values.append(raw)
    return values


def _project_objective(
    obj: dict[str, Any],
    locale: dict[str, Any],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
    tasks_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    maps_raw = obj.get("maps") if isinstance(obj.get("maps"), list) else []
    maps = [_named_ref(m, locale, kind="map") for m in maps_raw if _id_of(m)]
    item_refs = _objective_item_values(obj, quest_items or {})
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for raw in item_refs:
        if not _id_of(raw):
            continue
        ref = _named_ref(raw, locale, kind="item", quest_items=quest_items)
        ident = ref["id"]
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ref)
    count = obj.get("count")
    exit_status, exit_name = normalize_objective_exit(obj)
    target_names = [
        str(name).strip()
        for name in (obj.get("targetNames") or [])
        if str(name).strip()
    ]
    target = str(obj.get("target") or "").strip()
    if target and target not in target_names:
        target_names.append(target)
    skill_name, skill_level = _project_skill(obj.get("skillLevel") or obj.get("skill"))
    trader_raw = obj.get("trader")
    trader = (
        _named_ref(trader_raw, locale, kind="trader") if _id_of(trader_raw) else None
    )
    station_raw = obj.get("hideoutStation") or obj.get("station")
    hideout_station = (
        _named_ref(station_raw, locale, kind="station") if _id_of(station_raw) else None
    )
    related = _fail_task_ref(obj.get("task"), locale, tasks_by_id)
    obj_type = str(obj.get("type") or "")
    trader_level = _opt_int(obj.get("level")) if obj_type == "traderLevel" else None
    standing_cmp = None
    if obj_type == "traderStanding":
        standing_cmp = _project_number_compare(
            {"compareMethod": obj.get("compareMethod"), "value": obj.get("value")}
        )
    return {
        "id": str(obj.get("id") or ""),
        "type": obj_type,
        "description": _resolve_obj_description(obj, locale),
        "optional": _as_bool(obj.get("optional")),
        "count": _as_int(count) if count is not None and count != "" else None,
        "maps": maps,
        "items": items,
        "found_in_raid": _as_bool(obj.get("foundInRaid")) if "foundInRaid" in obj else None,
        "required_keys": _project_required_key_groups(
            obj.get("requiredKeys"), locale, quest_items=quest_items
        ),
        "exit_status": exit_status,
        "exit_name": exit_name,
        "zones": _project_zones(obj.get("zones"), locale),
        "possible_locations": _project_possible_locations(
            obj.get("possibleLocations"), locale
        ),
        "zone_names": _project_zone_names(obj.get("zoneNames")),
        "target_names": target_names,
        "body_parts": [
            str(part).strip()
            for part in (obj.get("bodyParts") or [])
            if str(part).strip()
        ],
        "shot_type": str(obj.get("shotType") or "").strip(),
        "distance": _project_number_compare(obj.get("distance")),
        "using_weapon": _named_refs(
            obj.get("usingWeapon"), locale, kind="item", quest_items=quest_items
        ),
        "using_weapon_mods": _named_ref_groups(
            obj.get("usingWeaponMods"), locale, kind="item", quest_items=quest_items
        ),
        "wearing": _named_ref_groups(
            obj.get("wearing"), locale, kind="item", quest_items=quest_items
        ),
        "not_wearing": _named_refs(
            obj.get("notWearing"), locale, kind="item", quest_items=quest_items
        ),
        "use_any": _named_refs(
            obj.get("useAny"), locale, kind="item", quest_items=quest_items
        ),
        "contains_all": _named_refs(
            obj.get("containsAll"), locale, kind="item", quest_items=quest_items
        ),
        "contains_category": _named_refs(
            obj.get("containsCategory"), locale, kind="category"
        ),
        "attributes": _project_attributes(obj.get("attributes")),
        "health_effect": _project_health_effect(obj.get("healthEffect")),
        "player_health_effect": _project_health_effect(obj.get("playerHealthEffect")),
        "enemy_health_effect": _project_health_effect(obj.get("enemyHealthEffect")),
        "time_from_hour": _opt_int(obj.get("timeFromHour")),
        "time_until_hour": _opt_int(obj.get("timeUntilHour")),
        "dog_tag_level": _opt_int(obj.get("dogTagLevel")),
        "min_durability": _opt_int(obj.get("minDurability")),
        "max_durability": _opt_int(obj.get("maxDurability")),
        "skill_name": skill_name,
        "skill_level": skill_level,
        "hideout_station": hideout_station,
        "station_level": _opt_int(obj.get("stationLevel")),
        "trader": trader,
        "trader_level": trader_level,
        "standing": standing_cmp,
        "player_level": _opt_int(obj.get("playerLevel")),
        "related_tasks": [related] if related else [],
        "related_status": [
            str(item).strip()
            for item in (obj.get("status") or [])
            if str(item).strip()
        ],
    }


def _fail_task_ref(
    value: Any,
    locale: dict[str, Any],
    tasks_by_id: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    ident = _id_of(value)
    if not ident:
        return None
    blob: dict[str, Any]
    if isinstance(value, dict):
        blob = dict(value)
        blob.setdefault("id", ident)
    else:
        blob = {"id": ident}
    other = (tasks_by_id or {}).get(ident)
    if isinstance(other, dict):
        if not str(blob.get("name") or "").strip():
            blob["name"] = other.get("name")
        if not str(blob.get("normalizedName") or "").strip():
            blob["normalizedName"] = other.get("normalizedName")
        if blob.get("trader") in (None, ""):
            blob["trader"] = other.get("trader")
    named = _named_ref(blob, locale, kind="task")
    if not named["id"]:
        return None
    trader_raw = blob.get("trader")
    trader_id = _id_of(trader_raw)
    trader_slug = ""
    trader_name = ""
    if trader_id:
        trader = _named_ref(trader_raw, locale, kind="trader")
        trader_id = str(trader.get("id") or trader_id)
        trader_slug = str(trader.get("slug") or "")
        trader_name = str(trader.get("name") or "")
    return {
        "id": named["id"],
        "slug": named.get("slug") or "",
        "name": named.get("name") or "",
        "trader_id": trader_id,
        "trader_slug": trader_slug,
        "trader_name": trader_name,
    }


def _project_fail_condition(
    obj: dict[str, Any],
    locale: dict[str, Any],
    *,
    tasks_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    exit_status, _exit_name = normalize_objective_exit(obj)
    task_ref = _fail_task_ref(obj.get("task"), locale, tasks_by_id)
    trader_raw = obj.get("trader")
    trader = (
        _named_ref(trader_raw, locale, kind="trader") if _id_of(trader_raw) else None
    )
    statuses = [
        str(item).strip()
        for item in (obj.get("status") or [])
        if str(item).strip()
    ]
    return {
        "id": str(obj.get("id") or ""),
        "type": str(obj.get("type") or ""),
        "description": _resolve_obj_description(obj, locale),
        "status": statuses,
        "tasks": [task_ref] if task_ref else [],
        "exit_status": exit_status,
        "trader": trader,
    }


def _project_fail_conditions(
    raw: Any,
    locale: dict[str, Any],
    *,
    tasks_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [
        _project_fail_condition(obj, locale, tasks_by_id=tasks_by_id)
        for obj in raw
        if isinstance(obj, dict)
    ]


def _project_point(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    x = _as_float(value.get("x"))
    z = _as_float(value.get("z"))
    if x is None or z is None:
        return None
    y = _as_float(value.get("y"))
    return {"x": x, "y": 0.0 if y is None else y, "z": z}


def _zone_dedupe_key(
    zone_id: str,
    point: dict[str, float] | None,
    outline: list[dict[str, float]],
) -> str:
    """json.tarkov.dev 常把同一触发区原样写两遍；同 id 但坐标不同的要保留。"""
    if point is not None:
        return f"{round(point['x'])}:{round(point['z'])}:{round(point['y'])}"
    if outline:
        cx = sum(item["x"] for item in outline) / len(outline)
        cz = sum(item["z"] for item in outline) / len(outline)
        return f"{round(cx)}:{round(cz)}"
    return f"id:{zone_id}" if zone_id else ""


def _project_zones(raw: Any, locale: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        map_ref = _named_ref(row.get("map"), locale, kind="map")
        point = _project_point(row.get("position"))
        outline = [
            pt
            for item in (row.get("outline") or [])
            if (pt := _project_point(item)) is not None
        ]
        if not point and not outline:
            continue
        zone_id = str(row.get("id") or "")
        dedupe = _zone_dedupe_key(zone_id, point, outline)
        if dedupe:
            if dedupe in seen:
                continue
            seen.add(dedupe)
        top = _as_float(row.get("top"))
        bottom = _as_float(row.get("bottom"))
        out.append(
            {
                "id": zone_id,
                "map_id": map_ref.get("id") or "",
                "map_slug": map_ref.get("slug") or "",
                "map_name": map_ref.get("name") or "",
                "x": None if not point else point["x"],
                "y": None if not point else point["y"],
                "z": None if not point else point["z"],
                "outline": outline,
                "top": top,
                "bottom": bottom,
            }
        )
    return out


def _project_possible_locations(raw: Any, locale: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        map_ref = _named_ref(row.get("map"), locale, kind="map")
        positions = [
            pt
            for item in (row.get("positions") or [])
            if (pt := _project_point(item)) is not None
        ]
        if not positions:
            continue
        out.append(
            {
                "map_id": map_ref.get("id") or "",
                "map_slug": map_ref.get("slug") or "",
                "map_name": map_ref.get("name") or "",
                "positions": positions,
            }
        )
    return out


def _project_zone_names(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _project_required_key_groups(
    raw: Any,
    locale: dict[str, Any],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> list[list[dict[str, str]]]:
    """目标 requiredKeys：外层多组（多扇门），内层为可替换钥匙（或）。"""
    if not isinstance(raw, list) or not raw:
        return []
    groups: list[list[dict[str, str]]] = []
    for group in raw:
        items = group if isinstance(group, list) else [group]
        refs = [
            _named_ref(i, locale, kind="item", quest_items=quest_items)
            for i in items
            if _id_of(i)
        ]
        if refs:
            groups.append(refs)
    return groups


def _needed_keys_from_objectives(
    objectives: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_map: dict[str, dict[str, Any]] = {}
    for obj in objectives:
        maps = obj.get("maps") if isinstance(obj.get("maps"), list) else []
        map_ref = maps[0] if maps else {"id": "", "slug": "", "name": ""}
        mid = str(map_ref.get("id") or "")
        bucket = by_map.setdefault(mid, {"map": map_ref, "keys": [], "_seen": set()})
        seen: set[str] = bucket["_seen"]
        for group in obj.get("required_keys") or []:
            for ref in group:
                ident = str(ref.get("id") or "").strip()
                if ident and ident not in seen:
                    seen.add(ident)
                    bucket["keys"].append(ref)
    return [
        {"map": row["map"], "keys": row["keys"]}
        for row in by_map.values()
        if row["keys"]
    ]


def _project_rewards(
    raw: Any,
    locale: dict[str, Any],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    out = _empty_rewards()
    if not isinstance(raw, dict):
        return out
    items_out: list[dict[str, Any]] = []
    for row in raw.get("items") or []:
        if not isinstance(row, dict):
            continue
        item_ref = _named_ref(
            row.get("item"), locale, kind="item", quest_items=quest_items
        )
        if not item_ref["id"]:
            continue
        items_out.append({**item_ref, "count": _as_int(row.get("count"), 1)})
    standing: list[dict[str, Any]] = []
    for row in raw.get("traderStanding") or []:
        if not isinstance(row, dict):
            continue
        trader = _named_ref(row.get("trader"), locale, kind="trader")
        standing.append({**trader, "standing": float(row.get("standing") or 0)})
    offers: list[dict[str, Any]] = []
    for row in raw.get("offerUnlock") or []:
        offer = _project_offer_unlock(row, locale, quest_items=quest_items)
        if offer:
            offers.append(offer)
    skills: list[dict[str, Any]] = []
    for row in raw.get("skillLevelReward") or []:
        name, level = _project_skill(row)
        if not name and level is None:
            continue
        skills.append({"name": name, "level": 0 if level is None else level})
    traders = _named_refs(raw.get("traderUnlock"), locale, kind="trader")
    crafts: list[dict[str, Any]] = []
    for row in raw.get("craftUnlock") or []:
        craft = _project_craft_unlock(row, locale, quest_items=quest_items)
        if craft:
            crafts.append(craft)
    achievements: list[dict[str, Any]] = []
    for row in raw.get("achievement") or []:
        ref = _project_image_ref(row, locale)
        if ref:
            achievements.append(ref)
    customizations: list[dict[str, Any]] = []
    for row in raw.get("customization") or []:
        ref = _project_image_ref(row, locale)
        if ref:
            customizations.append(ref)
    out.update(
        {
            "items": items_out,
            "trader_standing": standing,
            "offer_unlock": offers,
            "skill_level_reward": skills,
            "trader_unlock": traders,
            "craft_unlock": crafts,
            "achievement": achievements,
            "customization": customizations,
        }
    )
    return out


def _project_task_requirements(
    raw: Any,
    locale: dict[str, Any],
    *,
    tasks_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        ref = _fail_task_ref(row.get("task"), locale, tasks_by_id)
        if ref is None:
            continue
        ident = str(ref.get("id") or "").strip()
        if not ident or ident in seen:
            continue
        seen.add(ident)
        statuses = [
            str(item).strip()
            for item in (row.get("status") or [])
            if str(item).strip()
        ]
        out.append({**ref, "status": statuses})
    return out


def _collect_unlocks(
    task_id: str,
    locale: dict[str, Any],
    tasks_by_id: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not task_id or not tasks_by_id:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for other_id, other in tasks_by_id.items():
        if other_id == task_id or not isinstance(other, dict):
            continue
        reqs = other.get("taskRequirements")
        if not isinstance(reqs, list):
            continue
        matched: list[str] = []
        for req in reqs:
            if not isinstance(req, dict):
                continue
            if _id_of(req.get("task")) != task_id:
                continue
            matched.extend(
                str(item).strip()
                for item in (req.get("status") or [])
                if str(item).strip()
            )
        if not matched:
            continue
        if other_id in seen:
            continue
        seen.add(other_id)
        ref = _fail_task_ref(other, locale, tasks_by_id)
        if ref is None:
            continue
        out.append({**ref, "status": matched})
    out.sort(key=lambda row: (str(row.get("trader_slug") or ""), str(row.get("name") or "")))
    return out


_LOYALTY_REQ_TYPES = frozenset({"", "level", "loyaltyLevel", "loyalty"})


def task_min_trader_level(raw: dict[str, Any], trader_id: str = "") -> int:
    """任务所属商人的信任度等级。没有本商人要求时按游戏默认归到 1。"""
    blob = raw.get("traderRequirements")
    if not isinstance(blob, list):
        blob = raw.get("traderLevelRequirements")
    if not isinstance(blob, list):
        return 1
    own = (trader_id or "").strip()
    best = 0
    for row in blob:
        if not isinstance(row, dict):
            continue
        req_trader = _id_of(row.get("trader"))
        if own and req_trader and req_trader != own:
            continue
        req_type = str(row.get("requirementType") or row.get("type") or "").strip()
        if req_type not in _LOYALTY_REQ_TYPES:
            continue
        value = row.get("value")
        if value is None:
            value = row.get("level")
        level = _as_int(value)
        if level > best:
            best = level
    return best if best > 0 else 1


def _project_trader_requirements(
    raw: Any,
    locale: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        trader = _named_ref(row.get("trader"), locale, kind="trader")
        if not trader["id"] and not trader["slug"]:
            continue
        value = row.get("value")
        if value is None:
            value = row.get("level")
        req_type = str(row.get("requirementType") or row.get("type") or "").strip()
        out.append(
            {
                **trader,
                "requirement_type": req_type,
                "value": _as_number(value),
                "compare_method": str(row.get("compareMethod") or ""),
            }
        )
    return out


def project_task_detail(
    raw: dict[str, Any],
    locale: dict[str, Any],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
    tasks_by_id: dict[str, dict[str, Any]] | None = None,
    include_unlocks: bool = True,
) -> dict[str, Any] | None:
    summary = project_task_summary(raw, locale)
    if summary is None:
        return None
    locale = locale or {}
    objectives = [
        _project_objective(
            obj, locale, quest_items=quest_items, tasks_by_id=tasks_by_id
        )
        for obj in (raw.get("objectives") or [])
        if isinstance(obj, dict)
    ]
    keys_out: list[dict[str, Any]] = []
    for row in raw.get("neededKeys") or []:
        if not isinstance(row, dict):
            continue
        map_ref = _named_ref(row.get("map"), locale, kind="map")
        keys = [
            _named_ref(k, locale, kind="item", quest_items=quest_items)
            for k in (row.get("keys") or [])
            if _id_of(k)
        ]
        if keys:
            keys_out.append({"map": map_ref, "keys": keys})
    if not keys_out:
        keys_out = _needed_keys_from_objectives(objectives)
    delay_min = _opt_int(raw.get("availableDelaySecondsMin"))
    delay_max = _opt_int(raw.get("availableDelaySecondsMax"))
    summary.update(
        {
            "objectives": objectives,
            "trader_requirements": _project_trader_requirements(
                raw.get("traderRequirements") or raw.get("traderLevelRequirements"),
                locale,
            ),
            "task_requirements": _project_task_requirements(
                raw.get("taskRequirements"),
                locale,
                tasks_by_id=tasks_by_id,
            ),
            "unlocks": _collect_unlocks(summary["id"], locale, tasks_by_id)
            if include_unlocks
            else [],
            "start_rewards": _project_rewards(
                raw.get("startRewards"), locale, quest_items=quest_items
            ),
            "finish_rewards": _project_rewards(
                raw.get("finishRewards"), locale, quest_items=quest_items
            ),
            "fail_rewards": _project_rewards(
                raw.get("failureOutcome") or raw.get("failRewards"),
                locale,
                quest_items=quest_items,
            ),
            "needed_keys": keys_out,
            "fail_conditions": _project_fail_conditions(
                raw.get("failConditions"),
                locale,
                tasks_by_id=tasks_by_id,
            ),
            "restartable": _as_bool(raw.get("restartable")),
            "required_prestige": _project_prestige(raw.get("requiredPrestige"), locale),
            "available_delay_seconds_min": delay_min,
            "available_delay_seconds_max": delay_max,
        }
    )
    return summary


def parse_task_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locale = _locale_map(payload)
    rows: list[dict[str, Any]] = []
    for raw in _tasks_map(payload).values():
        row = project_task_summary(raw, locale)
        if row:
            rows.append(row)
    rows.sort(
        key=lambda r: (
            r.get("trader_slug") or "",
            int(r.get("min_trader_level") or 1),
            int(r.get("min_player_level") or 0),
            str(r.get("name") or ""),
        )
    )
    return rows


def filter_task_rows(
    rows: list[dict[str, Any]],
    *,
    trader: str | None = None,
    map_slug: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    trader_key = (trader or "").strip().lower()
    map_key = (map_slug or "").strip().lower()
    needle = (q or "").strip().lower()
    out: list[dict[str, Any]] = []
    for row in rows:
        if trader_key:
            slug = str(row.get("trader_slug") or "").lower()
            tid = str(row.get("trader_id") or "").lower()
            tname = str(row.get("trader_name") or "").lower()
            if trader_key not in {slug, tid} and trader_key not in tname:
                continue
        if map_key:
            slug = str(row.get("map_slug") or "").lower()
            mid = str(row.get("map_id") or "").lower()
            mname = str(row.get("map_name") or "").lower()
            if map_key not in {slug, mid} and map_key not in mname:
                continue
        if needle:
            blob = " ".join(
                [
                    str(row.get("name") or ""),
                    str(row.get("normalized_name") or ""),
                    str(row.get("id") or ""),
                    str(row.get("trader_name") or ""),
                    str(row.get("map_name") or ""),
                ]
            ).lower()
            if needle not in blob:
                continue
        out.append(row)
    return out


def sort_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple:
        try:
            loyalty = int(row.get("min_trader_level") or 1)
        except (TypeError, ValueError):
            loyalty = 1
        try:
            level = int(row.get("min_player_level") or 0)
        except (TypeError, ValueError):
            level = 0
        return (
            str(row.get("trader_slug") or ""),
            loyalty,
            level,
            str(row.get("name") or ""),
        )

    return sorted(rows, key=key)


def paginate_task_rows(
    rows: list[dict[str, Any]],
    *,
    page: int = 1,
    page_size: int = TASKS_PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    try:
        size = int(page_size)
    except (TypeError, ValueError):
        size = TASKS_PAGE_SIZE_DEFAULT
    size = max(1, min(size, TASKS_PAGE_SIZE_MAX))
    try:
        page_n = int(page)
    except (TypeError, ValueError):
        page_n = 1
    total = len(rows)
    last = max(1, (total + size - 1) // size) if total else 1
    page_n = max(1, min(page_n, last))
    start = (page_n - 1) * size
    return {
        "items": rows[start : start + size],
        "task_count": total,
        "page": page_n,
        "page_size": size,
    }


def unique_traders(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    for row in rows:
        slug = str(row.get("trader_slug") or "").strip()
        if not slug or slug in seen:
            continue
        seen[slug] = {
            "id": str(row.get("trader_id") or ""),
            "slug": slug,
            "name": str(row.get("trader_name") or slug),
        }
    order = [slug for slug, _name in TRADER_BY_ID.values()]
    ordered = [seen[s] for s in order if s in seen]
    extra = [v for k, v in seen.items() if k not in set(order)]
    extra.sort(key=lambda r: r["name"])
    return ordered + extra


def get_tasks_raw(db: Session) -> TarkovTasksRaw | None:
    from app.services.tarkov import upstream as upstream_svc

    return upstream_svc.load_raw_row(db, "tasks")


def _store_tasks_raw_payload(payload: dict[str, Any]) -> dict[str, Any]:
    store = {k: v for k, v in payload.items() if k != "locale"}
    if isinstance(store.get("data"), dict):
        return store
    tasks = store.get("tasks")
    if isinstance(tasks, (dict, list)):
        data: dict[str, Any] = {"tasks": tasks}
        quest_items = store.get("questItems")
        if quest_items is not None:
            data["questItems"] = quest_items
        return {"data": data}
    return store


def persist_tasks_bundle(db: Session, bundle: TasksUpstreamBundle) -> dict[str, Any]:
    from app.services.tarkov import upstream as upstream_svc

    rows = parse_task_rows(bundle.payload)
    if not rows:
        raise TarkovTasksError("未解析到任务数据")
    now = now_naive()
    upstream_svc.persist_raw(
        db,
        "tasks",
        _store_tasks_raw_payload(bundle.payload),
        source=bundle.source,
        note=bundle.note,
        commit=False,
    )
    upstream_svc.persist_locale_if_present(
        db,
        "tasks",
        bundle.payload,
        source=bundle.source,
        note=bundle.note,
    )
    db.commit()
    global _parsed_cache
    with _parsed_lock:
        _parsed_cache = None
        _raid_prep_cache.clear()
        _raid_prep_index_cache.clear()
    return {
        "task_count": len(rows),
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
        "note": bundle.note,
    }


def _sync_current_mode(db: Session) -> dict[str, Any]:
    logger.info("syncing tarkov tasks from upstream (%s)", parse_game_mode())
    return persist_tasks_bundle(db, download_json_api_tasks(lang="zh"))


def sync_from_upstream(db: Session, *, game_mode: str | None = None) -> dict[str, Any]:
    return run_for_modes(
        lambda: _sync_current_mode(db),
        game_mode=game_mode,
        error_cls=TarkovTasksError,
        label="任务",
    )


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    from app.services.tarkov import overlay as overlay_svc
    from app.services.tarkov import upstream as upstream_svc

    source, payload, synced, note = upstream_svc.load_main_payload(
        db,
        "tasks",
        error_cls=TarkovTasksError,
        missing="无任务 raw",
        invalid="任务 raw_json 无效",
    )
    return source, overlay_svc.apply_loaded_overlay(db, "tasks", payload), synced, note


def ensure_tasks(db: Session) -> None:
    if get_tasks_raw(db) is not None:
        return
    sync_from_upstream(db, game_mode=parse_game_mode())


def catalog_task_id_set(db: Session) -> set[str] | None:
    """当前图鉴任务 id（parse 前已合 overlay）。无 raw 时 None，进度接口不筛。"""
    if get_tasks_raw(db) is None:
        return None
    try:
        _source, rows, _locale, _synced, _note = load_parsed_tasks(db)
    except TarkovTasksError:
        return None
    return {
        str(row.get("id") or "").strip()
        for row in rows
        if str(row.get("id") or "").strip()
    }


def load_parsed_tasks(
    db: Session,
) -> tuple[str, list[dict[str, Any]], dict[str, Any], str | None, str | None]:
    global _parsed_cache
    ensure_tasks(db)
    row = get_tasks_raw(db)
    synced = row.synced_at.isoformat() if row and row.synced_at else None
    key = parsed_cache_key(db, synced)
    with _parsed_lock:
        cached = _parsed_cache
        if cached is not None and cached[0] == key:
            source, payload, synced_at, note = _load_payload(db)
            return source, cached[1], cached[2], synced_at, note
    source, payload, synced_at, note = _load_payload(db)
    rows = parse_task_rows(payload)
    locale = _locale_map(payload)
    with _parsed_lock:
        _parsed_cache = (key, rows, locale)
    return source, rows, locale, synced_at, note


def list_tasks(
    db: Session,
    *,
    trader: str | None = None,
    map_slug: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = TASKS_PAGE_SIZE_DEFAULT,
    layout: str | None = None,
) -> dict[str, Any]:
    source, rows, _locale, synced_at, note = load_parsed_tasks(db)
    filtered = filter_task_rows(
        rows,
        trader=trader,
        map_slug=map_slug,
        q=q,
    )
    ordered = sort_task_rows(filtered)
    layout_key = (layout or TASKS_LAYOUT_TABLE).strip().lower()
    if layout_key == TASKS_LAYOUT_ALL:
        paged = {
            "items": ordered,
            "task_count": len(ordered),
            "page": 1,
            "page_size": len(ordered) or TASKS_PAGE_SIZE_DEFAULT,
        }
    else:
        paged = paginate_task_rows(ordered, page=page, page_size=page_size)
    return {
        "items": paged["items"],
        "task_count": paged["task_count"],
        "page": paged["page"],
        "page_size": paged["page_size"],
        "traders": unique_traders(rows),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def task_has_map_markers(detail: dict[str, Any], map_slug: str) -> bool:
    keys, ids = map_match_keys(map_slug)
    if not keys and not ids:
        return False
    for obj in detail.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        for zone in obj.get("zones") or []:
            if not _map_ref_hits(zone, keys, ids):
                continue
            if zone.get("x") is not None and zone.get("z") is not None:
                return True
            if zone.get("outline"):
                return True
        for loc in obj.get("possible_locations") or []:
            if _map_ref_hits(loc, keys, ids) and loc.get("positions"):
                return True
    return False


def canonical_raid_map_slug(map_slug: str) -> str:
    """把短 id / 等价 slug 归一到 MAP_BY_ID 主 slug；未知则返回小写原值。"""
    keys, ids = map_match_keys(map_slug)
    for mid, (slug, _name) in MAP_BY_ID.items():
        if slug in keys or mid in ids:
            return slug
    return (map_slug or "").strip().lower()


def _named_map_from_location(row: dict[str, Any]) -> dict[str, Any] | None:
    ident = str(row.get("id") or row.get("map_id") or "").strip()
    slug = str(row.get("slug") or row.get("map_slug") or "").strip()
    name = str(row.get("name") or row.get("map_name") or "").strip()
    if not ident and not slug and not name:
        return None
    types = row.get("types")
    return {
        "id": ident,
        "slug": slug,
        "name": name,
        "icon_link": str(row.get("icon_link") or ""),
        "types": [str(t) for t in types if t is not None and str(t).strip()]
        if isinstance(types, list)
        else [],
    }


def _unique_map_refs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        item = _named_map_from_location(row)
        if item is None:
            continue
        key = (item["slug"] or item["id"] or item["name"]).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def crop_raid_prep_detail_for_map(
    detail: dict[str, Any],
    map_slug: str,
) -> dict[str, Any]:
    """按所选图裁剪 zones / needed_keys。其他图目标保留为无几何 stub，供跨图提示。

    目标顺序与 dump 一致，不把本图步骤提前。
    """
    keys, ids = map_match_keys(map_slug)
    if not keys and not ids:
        return detail
    objectives_out: list[dict[str, Any]] = []
    this_map: list[dict[str, Any]] = []
    for obj in detail.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        raw_maps = [m for m in (obj.get("maps") or []) if isinstance(m, dict)]
        raw_zones = [z for z in (obj.get("zones") or []) if isinstance(z, dict)]
        raw_locs = [
            loc for loc in (obj.get("possible_locations") or []) if isinstance(loc, dict)
        ]
        maps = [m for m in raw_maps if _map_ref_hits(m, keys, ids)]
        zones = [z for z in raw_zones if _map_ref_hits(z, keys, ids)]
        locs = [loc for loc in raw_locs if _map_ref_hits(loc, keys, ids)]
        has_any_map_ref = bool(raw_maps or raw_zones or raw_locs)
        map_refs = _unique_map_refs([*raw_maps, *raw_zones, *raw_locs])
        if has_any_map_ref and not (maps or zones or locs):
            if not map_refs:
                continue
            objectives_out.append(
                {
                    **obj,
                    "maps": map_refs,
                    "zones": [],
                    "possible_locations": [],
                }
            )
            continue
        cropped = {
            **obj,
            "maps": map_refs if map_refs else ([] if has_any_map_ref else raw_maps),
            "zones": zones,
            "possible_locations": locs,
        }
        objectives_out.append(cropped)
        this_map.append(cropped)
    needed = _needed_keys_from_objectives(this_map)
    needed = [
        row
        for row in needed
        if isinstance(row, dict)
        and (
            _map_ref_hits(
                row.get("map") if isinstance(row.get("map"), dict) else None,
                keys,
                ids,
            )
            or not str((row.get("map") or {}).get("id") or "").strip()
        )
    ]
    type_list: list[str] = []
    seen_types: set[str] = set()
    for obj in this_map:
        t = str(obj.get("type") or "").strip()
        if t and t not in seen_types:
            seen_types.add(t)
            type_list.append(t)
    return {
        **detail,
        "objectives": objectives_out,
        "needed_keys": needed,
        "objective_count": len(this_map),
        "objective_types": type_list
        if type_list
        else list(detail.get("objective_types") or []),
    }


def strip_raid_prep_geometry(row: dict[str, Any]) -> dict[str, Any]:
    """去掉 zone / 刷新点轮廓，保留物品与类型供总结。"""
    objectives_out: list[dict[str, Any]] = []
    for obj in row.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        objectives_out.append({**obj, "zones": [], "possible_locations": []})
    return {**row, "objectives": objectives_out}


RAID_PREP_CATALOG_KEYS = (
    "id",
    "name",
    "normalized_name",
    "trader_id",
    "trader_slug",
    "trader_name",
    "has_map_markers",
    "min_player_level",
    "objective_count",
    "objective_types",
)


def strip_raid_prep_catalog(row: dict[str, Any]) -> dict[str, Any]:
    """目录行：列表 / 筛选 / OCR 够用，不含目标正文和区轮廓。"""
    out: dict[str, Any] = {key: row.get(key) for key in RAID_PREP_CATALOG_KEYS}
    out.setdefault("id", "")
    out.setdefault("name", "")
    out.setdefault("has_map_markers", False)
    out["objectives"] = []
    out["needed_keys"] = []
    out["fail_conditions"] = list(row.get("fail_conditions") or [])
    return out


def collect_raid_prep_rows(
    payload: dict[str, Any],
    map_slug: str,
) -> tuple[str, list[dict[str, Any]]]:
    """按地图收联机大厅任务；纯投影，不读库。目标已按图裁剪。"""
    keys, ids = map_match_keys(map_slug)
    locale = _locale_map(payload)
    quest_items = _quest_items_map(payload)
    tasks = _tasks_map(payload)
    map_name = ""
    for mid, (slug, name) in MAP_BY_ID.items():
        if slug in keys or mid in ids:
            map_name = name
            break
    rows: list[dict[str, Any]] = []
    for raw in tasks.values():
        if not isinstance(raw, dict):
            continue
        detail = project_task_detail(
            raw,
            locale,
            quest_items=quest_items,
            tasks_by_id=tasks,
            include_unlocks=False,
        )
        if detail is None or not task_hits_map(detail, map_slug):
            continue
        detail = crop_raid_prep_detail_for_map(detail, map_slug)
        rows.append(
            {
                "id": detail["id"],
                "name": detail["name"],
                "normalized_name": detail.get("normalized_name") or "",
                "trader_id": detail.get("trader_id") or "",
                "trader_slug": detail.get("trader_slug") or "",
                "trader_name": detail.get("trader_name") or "",
                "map_id": detail.get("map_id") or "",
                "map_slug": detail.get("map_slug") or "",
                "map_name": detail.get("map_name") or "",
                "min_player_level": detail.get("min_player_level") or 0,
                "min_trader_level": detail.get("min_trader_level") or 1,
                "experience": detail.get("experience") or 0,
                "lightkeeper_required": bool(detail.get("lightkeeper_required")),
                "kappa_required": bool(detail.get("kappa_required")),
                "faction_name": detail.get("faction_name") or "Any",
                "task_image_link": detail.get("task_image_link") or "",
                "wiki_link": detail.get("wiki_link") or "",
                "objective_count": detail.get("objective_count") or 0,
                "objective_types": list(detail.get("objective_types") or []),
                "objectives": list(detail.get("objectives") or []),
                "needed_keys": list(detail.get("needed_keys") or []),
                "fail_conditions": list(detail.get("fail_conditions") or []),
                "has_map_markers": task_has_map_markers(detail, map_slug),
            }
        )
    rows.sort(
        key=lambda r: (
            not r.get("has_map_markers"),
            str(r.get("trader_slug") or ""),
            int(r.get("min_player_level") or 0),
            str(r.get("name") or ""),
        )
    )
    return map_name, rows


def raid_prep_room_map_slugs() -> list[str]:
    """联机大厅房间用的短 id（lab / night-factory），去重保序。"""
    out: list[str] = []
    seen: set[str] = set()
    for _mid, (slug, _name) in MAP_BY_ID.items():
        key = slug
        for group in MAP_SLUG_EQUIV_GROUPS:
            if slug in group:
                key = group[0]
                break
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def collect_raid_prep_task_index(
    payload: dict[str, Any],
) -> dict[str, dict[str, dict[str, str]]]:
    """一次扫描：地图短 id → {task_id: {name, trader_slug}}。不含区轮廓。"""
    slugs = raid_prep_room_map_slugs()
    out: dict[str, dict[str, dict[str, str]]] = {slug: {} for slug in slugs}
    locale = _locale_map(payload)
    quest_items = _quest_items_map(payload)
    for raw in _tasks_map(payload).values():
        if not isinstance(raw, dict):
            continue
        detail = project_task_detail(
            raw,
            locale,
            quest_items=quest_items,
        )
        if detail is None:
            continue
        tid = str(detail.get("id") or "").strip()
        if not tid:
            continue
        name = str(detail.get("name") or "").strip() or tid
        trader_slug = str(detail.get("trader_slug") or "").strip()
        meta = {"name": name, "trader_slug": trader_slug}
        for slug in slugs:
            if task_hits_map(detail, slug):
                out[slug][tid] = meta
    return out


def raid_prep_map_task_index(db: Session) -> dict[str, dict[str, dict[str, str]]]:
    """按当前 game_mode 读任务 raw 建瘦索引；无 raw 时各图空字典。"""
    slugs = raid_prep_room_map_slugs()
    empty: dict[str, dict[str, dict[str, str]]] = {slug: {} for slug in slugs}
    if get_tasks_raw(db) is None:
        return empty
    row = get_tasks_raw(db)
    synced = row.synced_at.isoformat() if row and row.synced_at else None
    key = parsed_cache_key(db, synced)
    with _parsed_lock:
        hit = _raid_prep_index_cache.get(key)
        if hit is not None:
            return hit
    try:
        _source, payload, _synced_at, _note = _load_payload(db)
    except TarkovTasksError:
        return empty
    index = collect_raid_prep_task_index(payload)
    with _parsed_lock:
        _raid_prep_index_cache[key] = index
    return index


def load_raid_prep_rows(
    db: Session,
    map_slug: str,
    *,
    ensure: bool = True,
) -> tuple[str, str, list[dict[str, Any]], str | None, str | None, dict[str, Any]]:
    """带按图缓存的联机大厅投影；返回 source, map_name, rows, synced_at, note, payload。"""
    if ensure:
        ensure_tasks(db)
    elif get_tasks_raw(db) is None:
        raise TarkovTasksError("无任务 raw")
    row = get_tasks_raw(db)
    synced = row.synced_at.isoformat() if row and row.synced_at else None
    key = parsed_cache_key(db, synced)
    canon = canonical_raid_map_slug(map_slug)
    keys, ids = map_match_keys(map_slug)
    if not ids:
        raise TarkovTasksError("地图无效")
    entry_key = f"{key}:{canon}"
    with _parsed_lock:
        hit = _raid_prep_cache.get(entry_key)
        if hit is not None:
            source, payload, synced_at, note = _load_payload(db)
            return source, hit[0], hit[1], synced_at, note, payload
    source, payload, synced_at, note = _load_payload(db)
    map_name, rows = collect_raid_prep_rows(payload, canon)
    with _parsed_lock:
        _raid_prep_cache[entry_key] = (map_name, rows)
    return source, map_name, rows, synced_at, note, payload


def raid_prep_task_ids_for_map(db: Session, map_slug: str) -> set[str] | None:
    """本地图联机大厅任务 id 集合。

    无本地任务 raw 时返回 None（调用方跳过校验，避免 claim 路径打上游）。
    """
    if get_tasks_raw(db) is None:
        return None
    try:
        _source, _name, rows, _synced, _note, _payload = load_raid_prep_rows(
            db, map_slug, ensure=False
        )
    except TarkovTasksError:
        return None
    return {
        str(row.get("id") or "").strip()
        for row in rows
        if str(row.get("id") or "").strip()
    }


def raid_prep_task_belongs_to_map(
    db: Session, map_slug: str, task_id: str
) -> bool | None:
    """任务是否出现在本地图联机大厅目录。

    房间没有 game_mode，认领时 ContextVar 也可能和列表请求不一致，
    因此 PVP / PVE 两份 raw 都认。两边都没有可用目录时返回 None，
    调用方跳过校验，避免 claim 路径打上游。
    """
    tid = (task_id or "").strip()
    if not tid:
        return False
    saw_catalog = False
    current = current_game_mode()
    modes = (current, *(mode for mode in GAME_MODES if mode != current))
    for mode in modes:
        with game_mode_scope(mode):
            ids = raid_prep_task_ids_for_map(db, map_slug)
            if ids is None:
                continue
            saw_catalog = True
            if tid in ids:
                return True
    if not saw_catalog:
        return None
    return False


def list_raid_prep(
    db: Session,
    map_slug: str,
    *,
    trader: str | None = None,
    q: str | None = None,
    types: list[str] | None = None,
    geometry: bool = False,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    map_slug = (map_slug or "").strip()
    if not map_slug:
        raise TarkovTasksError("地图无效")
    source, map_name, base_rows, synced_at, note, payload = load_raid_prep_rows(
        db, map_slug
    )
    # 缓存行是共享的；注解进度前浅拷贝，避免污染缓存
    wanted = {
        str(item).strip()
        for item in (task_ids or [])
        if str(item).strip()
    }
    if geometry:
        if not wanted:
            rows = []
        else:
            rows = [
                dict(row)
                for row in base_rows
                if str(row.get("id") or "").strip() in wanted
            ]
    else:
        rows = [strip_raid_prep_catalog(dict(row)) for row in base_rows]
    filtered = filter_task_rows(
        rows,
        trader=trader,
        q=q,
    )
    wanted_types = {
        str(t).strip()
        for t in (types or [])
        if str(t).strip()
    }
    if wanted_types:
        filtered = [
            row
            for row in filtered
            if wanted_types.intersection(row.get("objective_types") or [])
        ]
    ordered = sort_task_rows(filtered)
    ordered.sort(key=lambda r: not r.get("has_map_markers"))
    if geometry:
        _enrich_items_from_catalog(
            db, ordered, quest_items=_quest_items_map(payload)
        )
    return {
        "map_slug": map_slug,
        "map_name": map_name,
        "items": ordered,
        "task_count": len(ordered),
        "traders": unique_traders(base_rows),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def get_task_detail(
    db: Session,
    task_id: str,
) -> dict[str, Any]:
    task_id = (task_id or "").strip()
    if not task_id:
        raise TarkovTasksError("任务 id 无效")
    ensure_tasks(db)
    source, payload, _synced, _note = _load_payload(db)
    tasks = _tasks_map(payload)
    raw = tasks.get(task_id)
    if not isinstance(raw, dict):
        raise TarkovTasksError(f"未找到任务: {task_id}")
    detail = project_task_detail(
        raw,
        _locale_map(payload),
        quest_items=_quest_items_map(payload),
        tasks_by_id=tasks,
    )
    if detail is None:
        raise TarkovTasksError(f"未找到任务: {task_id}")
    detail["source"] = source
    quest_items = _quest_items_map(payload)
    _enrich_items_from_catalog(db, detail, quest_items=quest_items)
    _enrich_stations_from_hideout(db, detail)
    _enrich_crafts_from_guides(db, detail)
    _enrich_image_refs_from_extras(db, detail)
    return detail


def _iter_reward_item_refs(rewards: Any):
    if not isinstance(rewards, dict):
        return
    yield from rewards.get("items") or []
    for offer in rewards.get("offer_unlock") or []:
        if isinstance(offer, dict) and isinstance(offer.get("item"), dict):
            yield offer["item"]
    for craft in rewards.get("craft_unlock") or []:
        if isinstance(craft, dict) and isinstance(craft.get("item"), dict):
            yield craft["item"]


def _iter_named_item_refs(*details: dict[str, Any]):
    for detail in details:
        if not isinstance(detail, dict):
            continue
        for obj in detail.get("objectives") or []:
            if not isinstance(obj, dict):
                continue
            for group in obj.get("required_keys") or []:
                yield from group
            yield from obj.get("items") or []
            yield from obj.get("using_weapon") or []
            yield from obj.get("not_wearing") or []
            yield from obj.get("use_any") or []
            yield from obj.get("contains_all") or []
            for group in obj.get("using_weapon_mods") or []:
                yield from group
            for group in obj.get("wearing") or []:
                yield from group
        for row in detail.get("needed_keys") or []:
            yield from row.get("keys") or []
        for key in ("finish_rewards", "start_rewards", "fail_rewards"):
            yield from _iter_reward_item_refs(detail.get(key))


def _quest_item_hits(
    wanted: set[str],
    quest_items: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ident in wanted:
        raw = quest_items.get(ident)
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if _is_placeholder_name(ident, name):
            name = ""
        icon = str(
            raw.get("iconLink")
            or raw.get("icon_link")
            or raw.get("baseImageLink")
            or ""
        ).strip()
        types = raw.get("types") if isinstance(raw.get("types"), list) else []
        if not name and not icon:
            continue
        out[ident] = {
            "name": name,
            "icon_link": icon,
            "types": [str(t) for t in types if t is not None and str(t).strip()],
        }
    return out


def _apply_item_hits(
    refs: list[dict[str, Any]],
    found: dict[str, dict[str, Any]],
    *,
    prefer_hit_name: bool,
) -> None:
    for ref in refs:
        ident = str(ref.get("id") or "").strip()
        hit = found.get(ident)
        if not hit:
            continue
        name = str(hit.get("name") or "").strip()
        if name and not _is_placeholder_name(ident, name):
            if prefer_hit_name or _is_placeholder_name(
                ident, str(ref.get("name") or "")
            ):
                ref["name"] = name
        icon = str(hit.get("icon_link") or "").strip()
        if icon and (
            prefer_hit_name or not str(ref.get("icon_link") or "").strip()
        ):
            ref["icon_link"] = icon
        types = hit.get("types") if isinstance(hit.get("types"), list) else []
        if types and (prefer_hit_name or not ref.get("types")):
            ref["types"] = list(types)


def apply_item_hits_to_details(
    details: list[dict[str, Any]],
    found: dict[str, dict[str, Any]],
    *,
    prefer_hit_name: bool = True,
) -> None:
    """用物品目录命中结果回填任务里的钥匙 / 目标物品名。"""
    refs = [r for r in _iter_named_item_refs(*details) if isinstance(r, dict)]
    _apply_item_hits(refs, found, prefer_hit_name=prefer_hit_name)


def _lookup_item_hits_from_catalog(
    db: Session, wanted: set[str]
) -> dict[str, dict[str, Any]]:
    if not wanted:
        return {}
    try:
        from app.services.tarkov import upstream as upstream_svc
        from app.services.tarkov.catalog import _row_from_raw, iter_raw_items
        from app.services.tarkov.items import _locale_map as items_locale
    except Exception:  # noqa: BLE001
        return {}
    try:
        source, items_payload, _synced, _note = upstream_svc.load_main_payload(db, "items")
    except Exception:  # noqa: BLE001
        return {}
    locale = items_locale(items_payload)
    found: dict[str, dict[str, Any]] = {}
    try:
        for ident, raw in iter_raw_items(source, items_payload):
            if ident not in wanted or ident in found:
                continue
            hit = _row_from_raw(ident, raw, locale)
            if hit:
                found[ident] = hit
            if len(found) >= len(wanted):
                break
    except Exception:  # noqa: BLE001
        logger.warning("task item enrich: catalog unavailable", exc_info=True)
        return {}
    return found


def _enrich_items_from_catalog(
    db: Session,
    detail: dict[str, Any] | list[dict[str, Any]],
    *,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> None:
    """补物品中文名 / 图标 / types，供钥匙与奖励展示。"""
    rows = detail if isinstance(detail, list) else [detail]
    refs = [r for r in _iter_named_item_refs(*rows) if isinstance(r, dict)]
    wanted = {
        str(r.get("id") or "").strip()
        for r in refs
        if str(r.get("id") or "").strip()
    }
    if not wanted:
        return
    catalog_hits = _lookup_item_hits_from_catalog(db, wanted)
    if catalog_hits:
        _apply_item_hits(refs, catalog_hits, prefer_hit_name=True)
    qi_hits = _quest_item_hits(wanted, quest_items or {})
    if qi_hits:
        _apply_item_hits(refs, qi_hits, prefer_hit_name=False)


def _iter_station_refs(*details: dict[str, Any]):
    for detail in details:
        if not isinstance(detail, dict):
            continue
        for obj in detail.get("objectives") or []:
            if not isinstance(obj, dict):
                continue
            station = obj.get("hideout_station")
            if isinstance(station, dict) and str(station.get("id") or "").strip():
                yield station
        for key in ("finish_rewards", "start_rewards", "fail_rewards"):
            rewards = detail.get(key)
            if not isinstance(rewards, dict):
                continue
            for craft in rewards.get("craft_unlock") or []:
                if not isinstance(craft, dict):
                    continue
                station = craft.get("station")
                if isinstance(station, dict) and str(station.get("id") or "").strip():
                    yield station


def _id_map(blob: Any) -> dict[str, dict[str, Any]]:
    if isinstance(blob, dict):
        return {str(k): v for k, v in blob.items() if isinstance(v, dict)}
    if isinstance(blob, list):
        out: dict[str, dict[str, Any]] = {}
        for row in blob:
            if not isinstance(row, dict):
                continue
            ident = str(row.get("id") or "").strip()
            if ident:
                out[ident] = row
        return out
    return {}


def _apply_station_hit(ref: dict[str, Any], hit: dict[str, Any]) -> None:
    ident = str(ref.get("id") or "").strip()
    name = str(hit.get("name") or "").strip()
    slug = str(hit.get("slug") or "").strip()
    if slug:
        ref["slug"] = slug
    if name and not _is_placeholder_name(ident, name):
        ref["name"] = name


def _enrich_stations_from_hideout(db: Session, detail: dict[str, Any]) -> None:
    refs = [r for r in _iter_station_refs(detail) if isinstance(r, dict)]
    wanted = {
        str(r.get("id") or "").strip()
        for r in refs
        if str(r.get("id") or "").strip()
    }
    if not wanted:
        return
    try:
        from app.services.tarkov.guides import load_parsed_guides
    except Exception:  # noqa: BLE001
        return
    try:
        _source, parsed, _synced, _note = load_parsed_guides(db)
    except Exception:  # noqa: BLE001
        return
    by_id = {
        str(row.get("id") or "").strip(): row
        for row in (parsed.get("stations") or [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    for ref in refs:
        ident = str(ref.get("id") or "").strip()
        hit = by_id.get(ident)
        if hit:
            _apply_station_hit(ref, hit)


def _enrich_crafts_from_guides(db: Session, detail: dict[str, Any]) -> None:
    crafts: list[dict[str, Any]] = []
    for key in ("finish_rewards", "start_rewards", "fail_rewards"):
        rewards = detail.get(key)
        if not isinstance(rewards, dict):
            continue
        crafts.extend(
            row
            for row in (rewards.get("craft_unlock") or [])
            if isinstance(row, dict) and str(row.get("id") or "").strip()
        )
    if not crafts:
        return
    try:
        from app.services.tarkov.guides import load_parsed_guides
    except Exception:  # noqa: BLE001
        return
    try:
        _source, parsed, _synced, _note = load_parsed_guides(db)
    except Exception:  # noqa: BLE001
        return
    by_id = {
        str(row.get("id") or "").strip(): row
        for row in (parsed.get("crafts") or [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    for craft in crafts:
        hit = by_id.get(str(craft.get("id") or "").strip())
        if not hit:
            continue
        if not craft.get("level"):
            craft["level"] = int(hit.get("level") or 0)
        station = craft.get("station") if isinstance(craft.get("station"), dict) else {}
        slug = str(hit.get("station_slug") or "").strip()
        name = str(hit.get("station_name") or "").strip()
        sid = str(hit.get("station_id") or "").strip()
        if sid or slug or name:
            craft["station"] = {
                "id": sid or str(station.get("id") or ""),
                "slug": slug or str(station.get("slug") or ""),
                "name": name or str(station.get("name") or sid),
                "icon_link": str(station.get("icon_link") or ""),
                "types": list(station.get("types") or []),
            }
        if not isinstance(craft.get("item"), dict) or not str(
            (craft.get("item") or {}).get("id") or ""
        ).strip():
            offered = hit.get("product_item") or {}
            ident = str(offered.get("id") or "").strip()
            if ident:
                craft["item"] = {
                    "id": ident,
                    "slug": str(offered.get("slug") or ""),
                    "name": str(offered.get("name") or ident),
                    "icon_link": str(offered.get("icon_link") or ""),
                    "types": list(offered.get("types") or []),
                    "count": int(offered.get("count") or 1),
                }


def _iter_image_refs(*details: dict[str, Any]):
    for detail in details:
        if not isinstance(detail, dict):
            continue
        prestige = detail.get("required_prestige")
        if isinstance(prestige, dict) and str(prestige.get("id") or "").strip():
            yield "prestige", prestige
        for key in ("finish_rewards", "start_rewards", "fail_rewards"):
            rewards = detail.get(key)
            if not isinstance(rewards, dict):
                continue
            for row in rewards.get("achievement") or []:
                if isinstance(row, dict):
                    yield "achievements", row
            for row in rewards.get("customization") or []:
                if isinstance(row, dict):
                    yield "customization", row


def _enrich_image_refs_from_extras(db: Session, detail: dict[str, Any]) -> None:
    refs = list(_iter_image_refs(detail))
    if not refs:
        return
    try:
        from app.services.tarkov import upstream as upstream_svc
    except Exception:  # noqa: BLE001
        return
    payload = upstream_svc.load_raw(db, "extras")
    if not isinstance(payload, dict):
        return
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    catalogs = {
        "achievements": _id_map(data.get("achievements")),
        "prestige": _id_map(data.get("prestige")),
        "customization": _id_map(data.get("customization") or data.get("customizations")),
    }
    for kind, ref in refs:
        ident = str(ref.get("id") or "").strip()
        hit = catalogs.get(kind, {}).get(ident)
        if not isinstance(hit, dict):
            continue
        name = str(hit.get("name") or "").strip()
        icon = str(
            hit.get("imageLink")
            or hit.get("iconLink")
            or hit.get("image_link")
            or ""
        ).strip()
        if name and (
            not str(ref.get("name") or "").strip()
            or _is_placeholder_name(ident, str(ref.get("name") or ""))
        ):
            ref["name"] = name
        if icon and not str(ref.get("image_link") or "").strip():
            ref["image_link"] = icon
        level = hit.get("prestigeLevel")
        if level is not None and kind == "prestige" and not ref.get("prestige_level"):
            ref["prestige_level"] = _as_int(level)


def tasks_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=TASKS_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "task_count": result.get("task_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov tasks sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
