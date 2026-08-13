"""逃离塔科夫任务：回源 raw → 列表/详情投影。

优先 api.tarkov.dev GraphQL；失败回退 json.tarkov.dev/regular/tasks + tasks_zh。
失败不覆盖已有成功 raw。
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovTasksMeta, TarkovTasksRaw
from app.services.tarkov_ammo import SOURCE_GRAPHQL, SOURCE_JSON_API, TARKOV_GRAPHQL_URL

logger = logging.getLogger(__name__)

META_ROW_ID = 1
RAW_ROW_ID = 1
TASKS_JOB_KEY = "tarkov_tasks_sync"
TASKS_PAGE_SIZE_DEFAULT = 50
TASKS_PAGE_SIZE_MAX = 100
DOWNLOAD_TIMEOUT = 180

TARKOV_JSON_TASKS_URL = "https://json.tarkov.dev/regular/tasks"
TARKOV_JSON_TASKS_LOCALE_URL = "https://json.tarkov.dev/regular/tasks_{lang}"

_TASKS_QUERY = """
query TasksSync($lang: LanguageCode) {
  tasks(lang: $lang) {
    id
    name
    normalizedName
    wikiLink
    taskImageLink
    experience
    minPlayerLevel
    kappaRequired
    lightkeeperRequired
    factionName
    restartable
    trader { id name normalizedName imageLink }
    map { id name normalizedName }
    taskRequirements { status task { id name } }
    traderRequirements {
      requirementType
      compareMethod
      value
      trader { id name normalizedName }
    }
    objectives {
      id
      type
      description
      optional
      maps { id name normalizedName }
      ... on TaskObjectiveBasic { requiredKeys { id name iconLink } }
      ... on TaskObjectiveExtract {
        requiredKeys { id name iconLink }
        exitStatus
        exitName
        count
      }
      ... on TaskObjectiveItem {
        requiredKeys { id name iconLink }
        count
        foundInRaid
        items { id name iconLink }
        item { id name iconLink }
      }
      ... on TaskObjectiveMark {
        requiredKeys { id name iconLink }
        markerItem { id name iconLink }
      }
      ... on TaskObjectiveQuestItem {
        requiredKeys { id name iconLink }
        count
        questItem { id name shortName iconLink baseImageLink }
      }
      ... on TaskObjectiveShoot { requiredKeys { id name iconLink } count }
      ... on TaskObjectiveUseItem { requiredKeys { id name iconLink } }
    }
    finishRewards {
      traderStanding { standing trader { id name normalizedName } }
      items { count item { id name iconLink } }
    }
    neededKeys { map { id name } keys { id name } }
  }
}
"""

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

# 突袭图 id → slug / 中文名（与首页地图格对齐）
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
    "653e6760052c01c1c805532f": ("streets", "塔科夫街区"),
    "65b8d6f5cdde2479cb2a3125": ("ground-zero", "中心区"),
    "5714dc692459777137212e12": ("ground-zero", "中心区"),
    "6733700029c367a3d40b02af": ("labyrinth", "迷宫"),
    "69af492a4819ea4ba10a69c5": ("icebreaker", "破冰船"),
    "65cc8f81a9aac3e77d0cfd3e": ("terminal", "码头"),
    "68236e8153654e8c1200798a": ("ground-zero", "中心区"),
}

_parsed_lock = threading.Lock()
_parsed_cache: tuple[str, list[dict[str, Any]], dict[str, Any]] | None = None


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
    req_headers = {"User-Agent": "zhange-stats/1.0", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:  # noqa: BLE001
            detail = ""
        msg = f"下载失败 HTTP {exc.code}: {url}"
        if detail:
            msg = f"{msg} ({detail})"
        raise TarkovTasksError(msg) from exc
    except urllib.error.URLError as exc:
        raise TarkovTasksError(f"无法连接资源站: {exc}") from exc


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _locale_lookup(locale: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if not key:
            continue
        val = locale.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _is_placeholder_name(task_id: str, name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    if task_id and task_id in n and n.lower().endswith(" name"):
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


def parse_graphql_tasks(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("errors"):
        raise TarkovTasksError(f"tarkov.dev GraphQL 错误: {payload.get('errors')}")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise TarkovTasksError("tarkov.dev tasks 响应无效")
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        ident = str(raw.get("id") or "").strip()
        if ident:
            out[ident] = raw
    if not out:
        raise TarkovTasksError("tarkov.dev tasks 为空")
    return out


def download_graphql_tasks(*, lang: str = "zh") -> TasksUpstreamBundle:
    body = json.dumps(
        {"query": _TASKS_QUERY, "variables": {"lang": lang}},
        ensure_ascii=False,
    ).encode("utf-8")
    raw = _http_request(
        TARKOV_GRAPHQL_URL,
        method="POST",
        body=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=45,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovTasksError("tarkov.dev 任务响应解析失败") from exc
    if not isinstance(payload, dict):
        raise TarkovTasksError("tarkov.dev 任务响应格式无效")
    tasks = parse_graphql_tasks(payload)
    return TasksUpstreamBundle(
        source=SOURCE_GRAPHQL,
        payload={"format": "graphql", "data": {"tasks": list(tasks.values())}, "locale": {}},
        note="api.tarkov.dev GraphQL tasks",
    )


def download_json_api_tasks(*, lang: str = "zh") -> TasksUpstreamBundle:
    raw = _http_request(TARKOV_JSON_TASKS_URL, timeout=90)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovTasksError("json.tarkov.dev tasks 解析失败") from exc
    if not isinstance(payload, dict):
        raise TarkovTasksError("json.tarkov.dev tasks 格式无效")
    tasks = _tasks_map(payload)
    if not tasks:
        raise TarkovTasksError("json.tarkov.dev 未解析到任务")

    locale: dict[str, Any] = {}
    try:
        loc_raw = _http_request(
            TARKOV_JSON_TASKS_LOCALE_URL.format(lang=lang),
            timeout=60,
        )
        loc_payload = json.loads(loc_raw.decode("utf-8"))
        if isinstance(loc_payload, dict) and isinstance(loc_payload.get("data"), dict):
            locale = loc_payload["data"]
    except TarkovTasksError:
        logger.warning("json.tarkov.dev tasks_%s locale unavailable", lang)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("json.tarkov.dev tasks_%s locale parse failed", lang)

    quest_items = payload.get("questItems")
    if not isinstance(quest_items, (dict, list)):
        quest_items = {}

    return TasksUpstreamBundle(
        source=SOURCE_JSON_API,
        payload={"tasks": tasks, "locale": locale, "questItems": quest_items},
        note="json.tarkov.dev/regular/tasks",
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
        "experience": _as_int(raw.get("experience")),
        "kappa_required": _as_bool(raw.get("kappaRequired")),
        "lightkeeper_required": _as_bool(raw.get("lightkeeperRequired")),
        "faction_name": str(raw.get("factionName") or "Any"),
        "task_image_link": str(raw.get("taskImageLink") or ""),
        "wiki_link": str(raw.get("wikiLink") or ""),
        "objective_count": len(objectives),
        "task_requirements": _compact_task_requirements(raw),
    }


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


def _compact_task_requirements(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in raw.get("taskRequirements") or []:
        if not isinstance(row, dict):
            continue
        ident = _id_of(row.get("task"))
        if not ident:
            continue
        statuses = row.get("status") if isinstance(row.get("status"), list) else []
        out.append(
            {
                "id": ident,
                "status": [str(s).lower() for s in statuses if s is not None and str(s).strip()],
            }
        )
    return out


def tracker_task_flag(task_id: str, tasks: dict[str, Any]) -> str:
    """Tracker 条目 → complete / failed / invalid / active / uncompleted。"""
    tid = (task_id or "").strip()
    row = tasks.get(tid) if isinstance(tasks, dict) else None
    if not isinstance(row, dict):
        return "uncompleted"
    if row.get("complete"):
        return "complete"
    if row.get("failed"):
        return "failed"
    if row.get("invalid"):
        return "invalid"
    return "active"


def requirement_met(req: dict[str, Any], tasks: dict[str, Any]) -> bool:
    needed = [str(s).lower() for s in (req.get("status") or []) if str(s).strip()]
    if not needed:
        needed = ["complete"]
    return tracker_task_flag(str(req.get("id") or ""), tasks) in needed


PROGRESS_COMPLETE = "complete"
PROGRESS_AVAILABLE = "available"
PROGRESS_LOCKED = "locked"
PROGRESS_FAILED = "failed"
PROGRESS_STATUSES = {
    PROGRESS_COMPLETE,
    PROGRESS_AVAILABLE,
    PROGRESS_LOCKED,
    PROGRESS_FAILED,
}

# 进度开时默认顺序：进行中 → 缺少前置 → 已完成 → 已失败
PROGRESS_SORT_RANK = {
    PROGRESS_AVAILABLE: 0,
    PROGRESS_LOCKED: 1,
    PROGRESS_COMPLETE: 2,
    PROGRESS_FAILED: 3,
}


def classify_task_progress(row: dict[str, Any], progress: dict[str, Any]) -> str:
    """用 Tracker 进度 + 目录前置，标成已完成 / 进行中(可接取) / 缺少前置 / 已失败。

    商人 LL Tracker 不提供，不参与锁定。
    """
    tasks = progress.get("tasks") if isinstance(progress.get("tasks"), dict) else {}
    tid = str(row.get("id") or "")
    flag = tracker_task_flag(tid, tasks)
    if flag == "complete":
        return PROGRESS_COMPLETE
    if flag == "failed":
        return PROGRESS_FAILED
    faction = str(row.get("faction_name") or "Any").strip()
    pmc = str(progress.get("pmc_faction") or "").strip().upper()
    if faction and faction.lower() not in {"any", ""} and pmc and faction.upper() != pmc:
        return PROGRESS_LOCKED
    try:
        need_level = int(row.get("min_player_level") or 0)
    except (TypeError, ValueError):
        need_level = 0
    try:
        have_level = int(progress.get("player_level") or 1)
    except (TypeError, ValueError):
        have_level = 1
    if need_level and have_level < need_level:
        return PROGRESS_LOCKED
    for req in row.get("task_requirements") or []:
        if isinstance(req, dict) and not requirement_met(req, tasks):
            return PROGRESS_LOCKED
    if flag == "invalid":
        return PROGRESS_LOCKED
    return PROGRESS_AVAILABLE


def annotate_task_progress(
    rows: list[dict[str, Any]],
    progress: dict[str, Any],
) -> list[dict[str, Any]]:
    return [{**row, "progress_status": classify_task_progress(row, progress)} for row in rows]


def apply_requirement_progress(
    reqs: list[dict[str, Any]],
    progress: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks = progress.get("tasks") if isinstance(progress.get("tasks"), dict) else {}
    out: list[dict[str, Any]] = []
    for req in reqs:
        if not isinstance(req, dict):
            continue
        out.append({**req, "met": requirement_met(req, tasks)})
    return out


def _named_ref(value: Any, locale: dict[str, Any], *, kind: str) -> dict[str, str]:
    ident = _id_of(value)
    name = ""
    slug = ""
    if isinstance(value, dict):
        name = str(value.get("name") or "").strip()
        slug = str(value.get("normalizedName") or "").strip()
    if kind == "map" and ident:
        slug2, name2 = map_info(ident, value if isinstance(value, dict) else None)
        slug = slug or slug2
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
            name = ident
    icon = ""
    if isinstance(value, dict):
        icon = str(
            value.get("iconLink")
            or value.get("icon_link")
            or value.get("baseImageLink")
            or ""
        ).strip()
    return {"id": ident, "slug": slug, "name": name or ident, "icon_link": icon, "types": []}


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
) -> dict[str, Any]:
    maps_raw = obj.get("maps") if isinstance(obj.get("maps"), list) else []
    maps = [_named_ref(m, locale, kind="map") for m in maps_raw if _id_of(m)]
    item_refs = _objective_item_values(obj, quest_items or {})
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for raw in item_refs:
        if not _id_of(raw):
            continue
        ref = _named_ref(raw, locale, kind="item")
        ident = ref["id"]
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ref)
    count = obj.get("count")
    exit_status, exit_name = normalize_objective_exit(obj)
    return {
        "id": str(obj.get("id") or ""),
        "type": str(obj.get("type") or ""),
        "description": _resolve_obj_description(obj, locale),
        "optional": _as_bool(obj.get("optional")),
        "count": _as_int(count) if count is not None and count != "" else None,
        "maps": maps,
        "items": items,
        "found_in_raid": _as_bool(obj.get("foundInRaid")) if "foundInRaid" in obj else None,
        "required_keys": _project_required_key_groups(obj.get("requiredKeys"), locale),
        "exit_status": exit_status,
        "exit_name": exit_name,
    }


def _project_required_key_groups(raw: Any, locale: dict[str, Any]) -> list[list[dict[str, str]]]:
    """目标 requiredKeys：外层多组（多扇门），内层为可替换钥匙（或）。"""
    if not isinstance(raw, list) or not raw:
        return []
    groups: list[list[dict[str, str]]] = []
    for group in raw:
        items = group if isinstance(group, list) else [group]
        refs = [_named_ref(i, locale, kind="item") for i in items if _id_of(i)]
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


def _project_rewards(raw: Any, locale: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"items": [], "trader_standing": []}
    items_out: list[dict[str, Any]] = []
    for row in raw.get("items") or []:
        if not isinstance(row, dict):
            continue
        item_ref = _named_ref(row.get("item"), locale, kind="item")
        if not item_ref["id"]:
            continue
        items_out.append({**item_ref, "count": _as_int(row.get("count"), 1)})
    standing: list[dict[str, Any]] = []
    for row in raw.get("traderStanding") or []:
        if not isinstance(row, dict):
            continue
        trader = _named_ref(row.get("trader"), locale, kind="trader")
        standing.append({**trader, "standing": float(row.get("standing") or 0)})
    return {"items": items_out, "trader_standing": standing}


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
                "value": _as_int(value),
                "compare_method": str(row.get("compareMethod") or ""),
            }
        )
    return out


def _is_successor_status(statuses: list[str]) -> bool:
    """对齐 tarkov.dev：含 active 时仅 complete+active 算后续。"""
    if "active" in statuses:
        return len(statuses) == 2 and "complete" in statuses
    return True


def _successor_tasks(
    task_id: str,
    tasks_by_id: dict[str, dict[str, Any]],
    locale: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in tasks_by_id.values():
        if not isinstance(raw, dict):
            continue
        other_id = str(raw.get("id") or "").strip()
        if not other_id or other_id == task_id or other_id in seen:
            continue
        for row in raw.get("taskRequirements") or []:
            if not isinstance(row, dict):
                continue
            if _id_of(row.get("task")) != task_id:
                continue
            statuses = [
                str(s)
                for s in (row.get("status") or [])
                if s is not None and str(s).strip()
            ]
            if not _is_successor_status(statuses):
                continue
            other = project_task_summary(raw, locale)
            name = (other or {}).get("name") or other_id
            seen.add(other_id)
            out.append({"id": other_id, "name": name, "status": statuses})
            break
    out.sort(key=lambda r: str(r.get("name") or ""))
    return out


def project_task_detail(
    raw: dict[str, Any],
    locale: dict[str, Any],
    *,
    tasks_by_id: dict[str, dict[str, Any]] | None = None,
    quest_items: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    summary = project_task_summary(raw, locale)
    if summary is None:
        return None
    locale = locale or {}
    objectives = [
        _project_objective(obj, locale, quest_items=quest_items)
        for obj in (raw.get("objectives") or [])
        if isinstance(obj, dict)
    ]
    reqs: list[dict[str, Any]] = []
    for row in raw.get("taskRequirements") or []:
        if not isinstance(row, dict):
            continue
        task_ref = row.get("task")
        ident = _id_of(task_ref)
        if not ident:
            continue
        name = ""
        if isinstance(task_ref, dict):
            name = str(task_ref.get("name") or "")
        if tasks_by_id and ident in tasks_by_id:
            other = project_task_summary(tasks_by_id[ident], locale)
            if other:
                name = other["name"]
        if not name or _is_placeholder_name(ident, name):
            name = _locale_lookup(locale, f"{ident} name", f"{ident} Name") or ident
        statuses = row.get("status") if isinstance(row.get("status"), list) else []
        reqs.append(
            {
                "id": ident,
                "name": name,
                "status": [str(s) for s in statuses if s is not None],
            }
        )
    keys_out: list[dict[str, Any]] = []
    for row in raw.get("neededKeys") or []:
        if not isinstance(row, dict):
            continue
        map_ref = _named_ref(row.get("map"), locale, kind="map")
        keys = [
            _named_ref(k, locale, kind="item")
            for k in (row.get("keys") or [])
            if _id_of(k)
        ]
        if keys:
            keys_out.append({"map": map_ref, "keys": keys})
    if not keys_out:
        keys_out = _needed_keys_from_objectives(objectives)
    summary.update(
        {
            "objectives": objectives,
            "task_requirements": reqs,
            "successor_tasks": _successor_tasks(
                summary["id"], tasks_by_id or {}, locale
            ),
            "trader_requirements": _project_trader_requirements(
                raw.get("traderRequirements") or raw.get("traderLevelRequirements"),
                locale,
            ),
            "finish_rewards": _project_rewards(raw.get("finishRewards"), locale),
            "needed_keys": keys_out,
            "restartable": _as_bool(raw.get("restartable")),
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
    kappa: bool | None = None,
    q: str | None = None,
    progress_status: str | None = None,
) -> list[dict[str, Any]]:
    trader_key = (trader or "").strip().lower()
    map_key = (map_slug or "").strip().lower()
    needle = (q or "").strip().lower()
    status_key = (progress_status or "").strip().lower()
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
        if kappa is True and not row.get("kappa_required"):
            continue
        if kappa is False and row.get("kappa_required"):
            continue
        if status_key and str(row.get("progress_status") or "") != status_key:
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


def sort_task_rows(
    rows: list[dict[str, Any]],
    *,
    by_progress: bool = False,
) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple:
        try:
            level = int(row.get("min_player_level") or 0)
        except (TypeError, ValueError):
            level = 0
        rank = (
            PROGRESS_SORT_RANK.get(str(row.get("progress_status") or ""), 9)
            if by_progress
            else 0
        )
        return (
            rank,
            str(row.get("trader_slug") or ""),
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
    return (
        db.query(TarkovTasksRaw)
        .filter(TarkovTasksRaw.id == RAW_ROW_ID)
        .one_or_none()
    )


def get_tasks_meta(db: Session) -> TarkovTasksMeta | None:
    return (
        db.query(TarkovTasksMeta)
        .filter(TarkovTasksMeta.id == META_ROW_ID)
        .one_or_none()
    )


def _upsert_raw(
    db: Session,
    *,
    source: str,
    payload: dict[str, Any],
    note: str,
    synced_at,
) -> None:
    raw_json = json.dumps(payload, ensure_ascii=False)
    row = get_tasks_raw(db)
    if row is None:
        db.add(
            TarkovTasksRaw(
                id=RAW_ROW_ID,
                source=source,
                raw_json=raw_json,
                synced_at=synced_at,
                note=note,
            )
        )
    else:
        row.source = source
        row.raw_json = raw_json
        row.synced_at = synced_at
        row.note = note


def _upsert_meta(
    db: Session,
    *,
    source: str,
    task_count: int,
    note: str,
    synced_at,
) -> None:
    meta = get_tasks_meta(db)
    if meta is None:
        meta = TarkovTasksMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = source
    meta.task_count = task_count
    meta.synced_at = synced_at
    meta.note = note


def persist_tasks_bundle(db: Session, bundle: TasksUpstreamBundle) -> dict[str, Any]:
    rows = parse_task_rows(bundle.payload)
    if not rows:
        raise TarkovTasksError("未解析到任务数据")
    now = now_naive()
    _upsert_raw(
        db,
        source=bundle.source,
        payload=bundle.payload,
        note=bundle.note,
        synced_at=now,
    )
    _upsert_meta(
        db,
        source=bundle.source,
        task_count=len(rows),
        note=bundle.note,
        synced_at=now,
    )
    db.commit()
    global _parsed_cache
    with _parsed_lock:
        _parsed_cache = None
    return {
        "task_count": len(rows),
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
        "note": bundle.note,
    }


def sync_from_upstream(db: Session) -> dict[str, Any]:
    logger.info("syncing tarkov tasks from upstream")
    errors: list[str] = []
    try:
        return persist_tasks_bundle(db, download_graphql_tasks(lang="zh"))
    except TarkovTasksError as exc:
        errors.append(f"graphql: {exc}")
        logger.warning("tarkov.dev GraphQL tasks sync failed: %s", exc)
    try:
        bundle = download_json_api_tasks(lang="zh")
        note = bundle.note
        if errors:
            note = f"{note} (fallback; {errors[0][:160]})"
        return persist_tasks_bundle(
            db,
            TasksUpstreamBundle(source=bundle.source, payload=bundle.payload, note=note),
        )
    except TarkovTasksError as exc:
        detail = "；".join(errors) if errors else str(exc)
        raise TarkovTasksError(f"任务同步失败：{detail}；json 亦失败: {exc}") from None


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    row = get_tasks_raw(db)
    if row is None:
        raise TarkovTasksError("无任务 raw")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovTasksError("任务 raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovTasksError("任务 raw_json 格式无效")
    meta = get_tasks_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    note = (meta.note if meta else None) or row.note
    return row.source, payload, synced, note


def ensure_tasks(db: Session) -> None:
    if get_tasks_raw(db) is not None:
        return
    sync_from_upstream(db)


def load_parsed_tasks(
    db: Session,
) -> tuple[str, list[dict[str, Any]], dict[str, Any], str | None, str | None]:
    global _parsed_cache
    ensure_tasks(db)
    meta = get_tasks_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    key = synced or ""
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
    kappa: bool | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = TASKS_PAGE_SIZE_DEFAULT,
    progress: dict[str, Any] | None = None,
    progress_status: str | None = None,
    progress_bound: bool = False,
) -> dict[str, Any]:
    source, rows, _locale, synced_at, note = load_parsed_tasks(db)
    annotated = annotate_task_progress(rows, progress) if progress is not None else rows
    status_filter = (progress_status or "").strip().lower() if progress is not None else ""
    if status_filter and status_filter not in PROGRESS_STATUSES:
        status_filter = ""
    filtered = filter_task_rows(
        annotated,
        trader=trader,
        map_slug=map_slug,
        kappa=kappa,
        q=q,
        progress_status=status_filter or None,
    )
    ordered = sort_task_rows(filtered, by_progress=progress is not None)
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
        "progress_bound": bool(progress_bound),
        "progress_ready": progress is not None,
    }


def get_task_detail(
    db: Session,
    task_id: str,
    *,
    progress: dict[str, Any] | None = None,
    progress_bound: bool = False,
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
        tasks_by_id=tasks,
        quest_items=_quest_items_map(payload),
    )
    if detail is None:
        raise TarkovTasksError(f"未找到任务: {task_id}")
    detail["source"] = source
    _enrich_items_from_catalog(db, detail)
    detail["progress_bound"] = bool(progress_bound)
    detail["progress_ready"] = progress is not None
    if progress is not None:
        detail["progress_status"] = classify_task_progress(detail, progress)
        detail["task_requirements"] = apply_requirement_progress(
            list(detail.get("task_requirements") or []),
            progress,
        )
    return detail


def _iter_named_item_refs(detail: dict[str, Any]):
    for obj in detail.get("objectives") or []:
        for group in obj.get("required_keys") or []:
            yield from group
        yield from obj.get("items") or []
    for row in detail.get("needed_keys") or []:
        yield from row.get("keys") or []
    for item in (detail.get("finish_rewards") or {}).get("items") or []:
        yield item


def _enrich_items_from_catalog(db: Session, detail: dict[str, Any]) -> None:
    """补物品中文名 / 图标 / types，供钥匙与奖励展示。"""
    refs = [r for r in _iter_named_item_refs(detail) if isinstance(r, dict)]
    wanted = {
        str(r.get("id") or "").strip()
        for r in refs
        if str(r.get("id") or "").strip()
    }
    if not wanted:
        return
    try:
        from app.services.tarkov_catalog import _row_from_raw, iter_raw_items
        from app.services.tarkov_items import get_items_raw
        from app.services.tarkov_items import _locale_map as items_locale
    except Exception:  # noqa: BLE001
        return
    row = get_items_raw(db)
    if row is None:
        return
    try:
        items_payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(items_payload, dict):
        return
    locale = items_locale(items_payload)
    found: dict[str, dict[str, Any]] = {}
    try:
        for ident, raw in iter_raw_items(row.source, items_payload):
            if ident not in wanted or ident in found:
                continue
            hit = _row_from_raw(ident, raw, locale)
            if hit:
                found[ident] = hit
            if len(found) >= len(wanted):
                break
    except Exception:  # noqa: BLE001
        logger.warning("task item enrich: catalog unavailable", exc_info=True)
        return
    if not found:
        return
    for ref in refs:
        ident = str(ref.get("id") or "").strip()
        hit = found.get(ident)
        if not hit:
            continue
        name = str(hit.get("name") or "").strip()
        if name and (
            not str(ref.get("name") or "").strip()
            or str(ref.get("name") or "").strip() == ident
            or _is_placeholder_name(ident, str(ref.get("name") or ""))
        ):
            ref["name"] = name
        if hit.get("icon_link"):
            ref["icon_link"] = hit["icon_link"]
        if hit.get("types"):
            ref["types"] = list(hit["types"])


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
