"""塔科夫钥匙分包：api.tarkov.dev 门锁 / 入场钥按地图归包，目录补中文名。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov.ammo import TARKOV_GRAPHQL_URL
from app.services.tarkov.bosses import MAP_ZH
from app.services.tarkov.catalog import (
    KEYS_HANDBOOK_IDS,
    KEY_TYPES,
    load_parsed_catalog,
)
from app.services.tarkov.game_mode import (
    graphql_game_mode,
    json_resource_url,
    parse_game_mode,
)
from app.services.tarkov.guides import TarkovGuidesError, load_parsed_guides
from app.services.tarkov.http import download_bytes
from app.services.tarkov.items import TarkovItemsError
from app.services.tarkov.maps import HUB_SKIP, VARIANT_PARENT, resolve_map_slug
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov.tasks import TRADER_BY_ID, TarkovTasksError, load_parsed_tasks

logger = logging.getLogger(__name__)

_LOCKS_QUERY = """
query MapLocks($lang: LanguageCode, $gameMode: GameMode) {
  maps(lang: $lang, gameMode: $gameMode) {
    name
    normalizedName
    accessKeys { id name shortName iconLink }
    locks { lockType needsPower key { id name shortName iconLink } }
  }
}
""".strip()

_CACHE_TTL_SEC = 3600
_CACHE_VER = "locks-v3"
_lock_cache: dict[str, dict[str, Any]] = {}

SOURCE_GRAPHQL = "api.tarkov.dev maps.locks"
SOURCE_JSON = "json.tarkov.dev maps.locks"
SOURCE_STALE = "stale cache"
UNAVAILABLE_MSG = "钥匙分类暂时拉不到门锁数据（tarkov.dev 接口不可用）。请稍后再试。"

# 门锁 / 入场钥未收录时的第二优先：eftarkov.com 物品页面包屑（海岸线/海关/街区/储备站/破冰船钥匙）。
# 不在运行时爬站。官方 locks / accessKeys 已绑定的 id 不会被覆盖。
COMMUNITY_KEY_MAPS: dict[str, str] = {
    "5a0ea69f86f7741cd5406619": "shoreline",  # 疗养院东楼 108
    "5a0ee62286f774369454a7ac": "shoreline",  # 东 209
    "5a0ee72c86f77436955d3435": "shoreline",  # 东 213
    "5a0ee76686f7743698200d5c": "shoreline",  # 东 216
    "5a0eedb386f77403506300be": "shoreline",  # 东 322
    "5a0ec70e86f7742c0b518fba": "shoreline",  # 西 207
    "5a0eeb1a86f774688b70aa5c": "shoreline",  # 西 303
    "5a0eeb8e86f77461257ed71a": "shoreline",  # 西 309
    "5a13ee1986f774794d4c14cd": "shoreline",  # 西 323
    "5a0eebed86f77461230ddb3d": "shoreline",  # 西 325
    "5a0f006986f7741ffd2fe484": "shoreline",  # 气象站保险箱
    "5a0f045e86f7745b0f0d0e42": "shoreline",  # 加油站保险箱
    "5a0f075686f7745bcc42ee12": "shoreline",  # 商店保险箱
    "69bb3e54d6c67f6265004ab9": "icebreaker",  # Boreas 轮机舱
    "69bb3ec9f609db77390b0e1a": "icebreaker",  # Boreas 载员舱
    "69bb3f278af9f360ee010a7a": "icebreaker",  # C-1
    "69bb3f7df94327bc0f0230c9": "icebreaker",  # C-3
    "68e9654d72488961110dbf69": "reserve",  # RB-PKPTS
    "5d80cb8786f774405611c7d9": "reserve",  # RB-PP
    "591ae8f986f77406f854be45": "woods",  # Yotota 车钥匙
    "6939948dc2ceb9acd7082eb2": "woods",  # 旧屋厕所
    "57a349b2245977762b199ec7": "factory",  # 泵站前门
    "593858c486f774253a24cb52": "factory",  # 泵站后门
    "5a0eb38b86f774153b320eb0": "shoreline",  # SMW 车钥匙
    "67e183377c6c2011970f3149": "the-labyrinth",  # 阿里阿德涅之线
    "6866ad3853330f9b83064cf9": "terminal",  # 黑色军团钥匙卡
    "6866adbe09b973bf45094339": "terminal",  # 码头大门
    "68cc09872bdcc15c010c2668": "interchange",  # 14-4 KORD 修复
    "68c165f1903341d88b092b2a": "streets-of-tarkov",  # Cardinal
    "68e96180901b9b10270f1eed": "streets-of-tarkov",  # 邪教受害者公寓
    "63a39f18c2d53c2c6839c1d3": "streets-of-tarkov",  # 酒店 206
    "6391fcf5744e45201147080f": "streets-of-tarkov",  # Primorsky 大道公寓
    "68e960db934bf7b02d005dab": "streets-of-tarkov",  # Zmeisky 巷 3
    "67ee7680562d5057e60ccc3a": "streets-of-tarkov",  # TerraGroup 集团公寓
    "68e63b56ad8cba49190ea529": "streets-of-tarkov",  # 俄邮车
    "68e95d71a3d110355b03e529": "streets-of-tarkov",  # Elektronik
    "68e95f4fa4a577e907015787": "customs",  # Reshala 窝棚
    "5913915886f774123603c392": "customs",  # 军事基地检查站
}


class TarkovKeyPacksError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _http_request(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> bytes:
    return download_bytes(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout=timeout,
        error_cls=TarkovKeyPacksError,
    )


def _cache_key(mode: str) -> str:
    return f"{mode}:{_CACHE_VER}"


def parent_map_slug(slug: str) -> str:
    key = resolve_map_slug(slug)
    return VARIANT_PARENT.get(key, key)


def _english_from_slug(slug: str) -> str:
    return slug.replace("-", " ").title()


def _item_ref(raw: Any) -> dict[str, str] | None:
    if isinstance(raw, str):
        ident = raw.strip()
        if not ident:
            return None
        return {"id": ident, "name": "", "short_name": "", "icon_link": ""}
    if not isinstance(raw, dict):
        return None
    ident = str(raw.get("id") or raw.get("_id") or "").strip()
    if not ident:
        return None
    return {
        "id": ident,
        "name": str(raw.get("name") or ""),
        "short_name": str(raw.get("shortName") or raw.get("short_name") or ""),
        "icon_link": str(raw.get("iconLink") or raw.get("icon_link") or ""),
    }


def _catalog_uses(row: dict[str, Any] | None) -> int | None:
    if not row:
        return None
    props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
    raw = props.get("uses") if isinstance(props, dict) else None
    if raw is None:
        raw = row.get("uses")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def empty_key_sources() -> dict[str, Any]:
    return {"barters": [], "crafts": [], "tasks": [], "flea": None}


def _hydrate_key(
    ref: dict[str, str],
    catalog_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cat = catalog_by_id.get(ref["id"])
    uses = _catalog_uses(cat)
    if cat:
        types = [str(t) for t in (cat.get("types") or []) if t]
        if not types:
            types = ["keys"]
        return {
            "id": ref["id"],
            "name": str(cat.get("name") or ref.get("name") or ref["id"]),
            "short_name": str(cat.get("short_name") or ref.get("short_name") or ""),
            "icon_link": str(cat.get("icon_link") or ref.get("icon_link") or ""),
            "types": types,
            "uses": uses,
            "description": str(cat.get("description") or ""),
            "community": False,
            "sources": empty_key_sources(),
            "used_in_tasks": [],
        }
    return {
        "id": ref["id"],
        "name": str(ref.get("name") or ref["id"]),
        "short_name": str(ref.get("short_name") or ""),
        "icon_link": str(ref.get("icon_link") or ""),
        "types": ["keys"],
        "uses": uses,
        "description": "",
        "community": False,
        "sources": empty_key_sources(),
        "used_in_tasks": [],
    }


def _is_handbook_key(row: dict[str, Any]) -> bool:
    handbook = {str(x) for x in (row.get("handbook_ids") or []) if x}
    types = {str(x).strip().lower() for x in (row.get("types") or []) if x}
    return bool(handbook & KEYS_HANDBOOK_IDS) or bool(types & KEY_TYPES)


def _catalog_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ident = str(row.get("id") or "").strip()
        if ident:
            out[ident] = row
    return out


def _ensure_pack(packs: dict[str, dict[str, Any]], slug: str) -> dict[str, Any]:
    pack = packs.get(slug)
    if pack is None:
        pack = {
            "slug": slug,
            "name": MAP_ZH.get(slug) or slug,
            "english": _english_from_slug(slug),
            "keys": {},
        }
        packs[slug] = pack
    elif not pack["name"]:
        pack["name"] = MAP_ZH.get(slug) or pack["english"] or slug
    return pack


def _apply_community_binds(
    packs: dict[str, dict[str, Any]],
    bound_ids: set[str],
    catalog_by_id: dict[str, dict[str, Any]],
    *,
    has_catalog: bool,
) -> None:
    if not has_catalog:
        return
    for item_id, slug in COMMUNITY_KEY_MAPS.items():
        if item_id in bound_ids:
            continue
        cat = catalog_by_id.get(item_id)
        if not cat or not _is_handbook_key(cat):
            continue
        pack = _ensure_pack(packs, slug)
        entry = _ensure_entry(
            pack["keys"],
            {
                "id": item_id,
                "name": str(cat.get("name") or ""),
                "short_name": str(cat.get("short_name") or ""),
                "icon_link": str(cat.get("icon_link") or ""),
            },
            catalog_by_id,
        )
        entry["community"] = True
        bound_ids.add(item_id)


def _ensure_entry(
    pack_keys: dict[str, dict[str, Any]],
    ref: dict[str, str],
    catalog_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ident = ref["id"]
    entry = pack_keys.get(ident)
    if entry is None:
        entry = {
            **_hydrate_key(ref, catalog_by_id),
            "lock_count": 0,
            "access": False,
            "lock_types": [],
            "needs_power": False,
        }
        pack_keys[ident] = entry
    return entry


def group_key_packs(
    gql_maps: list[Any],
    catalog_rows: list[dict[str, Any]] | None = None,
    *,
    skip: set[str] | None = None,
    variant_parent: dict[str, str] | None = None,
) -> dict[str, Any]:
    """门锁 / 入场钥按母图归包；社区百科为第二优先；其余手册钥匙进 unbound。"""
    skip_slugs = skip if skip is not None else HUB_SKIP
    parents = variant_parent if variant_parent is not None else VARIANT_PARENT
    catalog_by_id = _catalog_index(catalog_rows or [])
    packs: dict[str, dict[str, Any]] = {}
    bound_ids: set[str] = set()

    for raw in gql_maps:
        if not isinstance(raw, dict):
            continue
        slug = resolve_map_slug(str(raw.get("normalizedName") or ""))
        if not slug or slug in skip_slugs:
            continue
        parent = parents.get(slug, slug)
        if parent in skip_slugs:
            continue
        pack = packs.get(parent)
        if pack is None:
            pack = {
                "slug": parent,
                "name": "",
                "english": _english_from_slug(parent),
                "keys": {},
            }
            packs[parent] = pack
        if slug == parent:
            pack["name"] = str(raw.get("name") or "") or pack["name"] or parent
        elif not pack["name"]:
            pack["name"] = str(raw.get("name") or "") or parent

        pack_keys = pack["keys"]
        for lock in raw.get("locks") or []:
            if not isinstance(lock, dict):
                continue
            ref = _item_ref(lock.get("key"))
            if not ref:
                continue
            bound_ids.add(ref["id"])
            entry = _ensure_entry(pack_keys, ref, catalog_by_id)
            entry["lock_count"] = int(entry.get("lock_count") or 0) + 1
            lock_type = str(lock.get("lockType") or lock.get("lock_type") or "").strip()
            if lock_type:
                types = entry.setdefault("lock_types", [])
                if lock_type not in types:
                    types.append(lock_type)
            if lock.get("needsPower") or lock.get("needs_power"):
                entry["needs_power"] = True

        for access in raw.get("accessKeys") or []:
            ref = _item_ref(access)
            if not ref:
                continue
            bound_ids.add(ref["id"])
            entry = _ensure_entry(pack_keys, ref, catalog_by_id)
            entry["access"] = True

    _apply_community_binds(
        packs, bound_ids, catalog_by_id, has_catalog=bool(catalog_rows)
    )

    maps_out: list[dict[str, Any]] = []
    for pack in packs.values():
        keys = list(pack["keys"].values())
        keys.sort(key=lambda row: (str(row.get("name") or ""), str(row.get("id") or "")))
        maps_out.append(
            {
                "slug": pack["slug"],
                "name": pack["name"] or pack["slug"],
                "english": pack["english"],
                "keys": keys,
            }
        )
    maps_out.sort(key=lambda row: (str(row.get("name") or ""), str(row.get("slug") or "")))

    unbound: list[dict[str, Any]] = []
    for row in catalog_rows or []:
        ident = str(row.get("id") or "").strip()
        if not ident or ident in bound_ids or not _is_handbook_key(row):
            continue
        unbound.append(
            {
                **_hydrate_key(
                    {
                        "id": ident,
                        "name": str(row.get("name") or ""),
                        "short_name": str(row.get("short_name") or ""),
                        "icon_link": str(row.get("icon_link") or ""),
                    },
                    catalog_by_id,
                ),
                "lock_count": 0,
                "access": False,
                "lock_types": [],
                "needs_power": False,
            }
        )
    unbound.sort(key=lambda row: (str(row.get("name") or ""), str(row.get("id") or "")))
    return {"maps": maps_out, "unbound": unbound}


def _trader_label(trader_id: str, slug: str, name: str) -> str:
    mapped = TRADER_BY_ID.get(trader_id)
    if mapped:
        full = mapped[1]
        if "（" in full and full.endswith("）"):
            return full.rsplit("（", 1)[1][:-1] or mapped[0]
        return full
    return name or slug or trader_id


def _task_source_name(row: dict[str, Any]) -> str:
    task_id = str(row.get("id") or "").strip()
    name = str(row.get("name") or "").strip()
    if task_id and tasks_svc._is_placeholder_name(task_id, name):
        slug = str(row.get("normalizedName") or row.get("normalized_name") or "").strip()
        return slug.replace("-", " ").title() if slug else ""
    return name


def _task_reward_item_ids(row: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(raw: Any) -> None:
        ident = ""
        if isinstance(raw, str):
            ident = raw.strip()
        elif isinstance(raw, dict):
            ident = str(raw.get("id") or raw.get("_id") or "").strip()
        if ident and ident not in seen:
            seen.add(ident)
            out.append(ident)

    projected = row.get("finish_rewards")
    if isinstance(projected, dict):
        for item in projected.get("items") or []:
            if isinstance(item, dict):
                add(item)
    raw_fr = row.get("finishRewards")
    if isinstance(raw_fr, dict):
        for item in raw_fr.get("items") or []:
            if isinstance(item, dict):
                add(item.get("item") if item.get("item") is not None else item)
            else:
                add(item)
    return out


def _catalog_flea(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    types = {str(t) for t in (row.get("types") or []) if t}
    if "noFlea" in types:
        return None
    price = None
    for key in ("last_low_price", "avg24h_price"):
        try:
            value = int(row.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            price = value
            break
    return {"price": price}


def _dedup_barters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("trader_slug") or row.get("trader_name") or "")
        prev = best.get(key)
        level = int(row.get("min_trader_level") or 0)
        if prev is None or level < int(prev.get("min_trader_level") or 0):
            best[key] = row
    return list(best.values())


def _dedup_named(rows: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        ident = tuple(str(row.get(k) or "") for k in keys)
        if ident in seen:
            continue
        seen.add(ident)
        out.append(row)
    return out


def build_key_source_index(
    *,
    barters: list[dict[str, Any]] | None = None,
    crafts: list[dict[str, Any]] | None = None,
    task_rows: list[dict[str, Any]] | None = None,
    catalog_rows: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """物品 id → 交换 / 制作 / 任务奖励 / 跳蚤（跳蚤不分钥匙等级）。"""
    out: dict[str, dict[str, Any]] = {}

    def bucket(item_id: str) -> dict[str, Any]:
        entry = out.get(item_id)
        if entry is None:
            entry = empty_key_sources()
            out[item_id] = entry
        return entry

    for raw in barters or []:
        offered = raw.get("offered_item") if isinstance(raw.get("offered_item"), dict) else {}
        item_id = str(offered.get("id") or "").strip()
        if not item_id:
            continue
        trader_id = str(raw.get("trader_id") or "")
        slug = str(raw.get("trader_slug") or "")
        bucket(item_id)["barters"].append(
            {
                "trader_slug": slug,
                "trader_name": _trader_label(
                    trader_id, slug, str(raw.get("trader_name") or "")
                ),
                "min_trader_level": int(raw.get("min_trader_level") or 0),
            }
        )

    for raw in crafts or []:
        product = raw.get("product_item") if isinstance(raw.get("product_item"), dict) else {}
        item_id = str(product.get("id") or "").strip()
        if not item_id:
            continue
        bucket(item_id)["crafts"].append(
            {
                "station_slug": str(raw.get("station_slug") or ""),
                "station_name": str(raw.get("station_name") or ""),
                "level": int(raw.get("level") or 0),
            }
        )

    for raw in task_rows or []:
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("id") or "").strip()
        if not task_id:
            continue
        name = _task_source_name(raw) or task_id
        reward = {"id": task_id, "name": name}
        for item_id in _task_reward_item_ids(raw):
            bucket(item_id)["tasks"].append(reward)

    for row in catalog_rows or []:
        item_id = str(row.get("id") or "").strip()
        if not item_id:
            continue
        flea = _catalog_flea(row)
        if flea is not None:
            bucket(item_id)["flea"] = flea

    for entry in out.values():
        entry["barters"] = _dedup_barters(entry["barters"])
        entry["crafts"] = _dedup_named(entry["crafts"], "station_slug", "level")
        entry["tasks"] = _dedup_named(entry["tasks"], "id")
    return out


def attach_key_sources(
    grouped: dict[str, Any],
    index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    for pack in grouped.get("maps") or []:
        if not isinstance(pack, dict):
            continue
        for key in pack.get("keys") or []:
            if isinstance(key, dict):
                key["sources"] = index.get(str(key.get("id") or "")) or empty_key_sources()
    for key in grouped.get("unbound") or []:
        if isinstance(key, dict):
            key["sources"] = index.get(str(key.get("id") or "")) or empty_key_sources()
    return grouped


def _item_id(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        return str(raw.get("id") or raw.get("_id") or "").strip()
    return ""


def _iter_required_key_ids(groups: Any) -> list[str]:
    out: list[str] = []
    for group in groups or []:
        items = group if isinstance(group, list) else [group]
        for item in items:
            ident = _item_id(item)
            if ident:
                out.append(ident)
    return out


def _objective_note(obj: dict[str, Any], locale: dict[str, Any] | None) -> str:
    oid = str(obj.get("id") or "").strip()
    note = str(obj.get("description") or "").strip()
    if locale:
        resolved = tasks_svc._resolve_obj_description(obj, locale)
        if resolved:
            note = resolved
    if not note or note == oid:
        return ""
    if oid and tasks_svc._is_placeholder_name(oid, note):
        return ""
    if note.endswith(" description") or note.endswith(" Description"):
        return ""
    return note


def _required_key_hits(
    row: dict[str, Any],
    locale: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for needed in row.get("neededKeys") or row.get("needed_keys") or []:
        if not isinstance(needed, dict):
            continue
        for key in needed.get("keys") or []:
            ident = _item_id(key)
            if ident:
                hits.append((ident, ""))
    for obj in row.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        if "requiredKeys" in obj:
            groups = obj.get("requiredKeys")
        else:
            groups = obj.get("required_keys")
        ids = _iter_required_key_ids(groups)
        if not ids:
            continue
        note = _objective_note(obj, locale)
        for ident in ids:
            hits.append((ident, note))
    return hits


def build_key_usage_index(
    task_rows: list[dict[str, Any]] | None = None,
    *,
    locale: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """物品 id → 需要这把钥匙的任务（目标说明可反查房间 / 门）。"""
    buckets: dict[str, dict[str, dict[str, Any]]] = {}
    for raw in task_rows or []:
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("id") or "").strip()
        if not task_id:
            continue
        name = _task_source_name(raw) or task_id
        for key_id, note in _required_key_hits(raw, locale):
            task = buckets.setdefault(key_id, {}).setdefault(
                task_id,
                {"id": task_id, "name": name, "notes": []},
            )
            if note and note not in task["notes"] and len(task["notes"]) < 6:
                task["notes"].append(note)
    out: dict[str, list[dict[str, Any]]] = {}
    for key_id, tasks in buckets.items():
        rows = list(tasks.values())
        rows.sort(key=lambda row: (str(row.get("name") or ""), str(row.get("id") or "")))
        out[key_id] = rows
    return out


def attach_key_usage(
    grouped: dict[str, Any],
    index: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    for pack in grouped.get("maps") or []:
        if not isinstance(pack, dict):
            continue
        for key in pack.get("keys") or []:
            if isinstance(key, dict):
                key["used_in_tasks"] = [
                    dict(row) for row in (index.get(str(key.get("id") or "")) or [])
                ]
    for key in grouped.get("unbound") or []:
        if isinstance(key, dict):
            key["used_in_tasks"] = [
                dict(row) for row in (index.get(str(key.get("id") or "")) or [])
            ]
    return grouped


def parse_locks_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("errors"):
        raise TarkovKeyPacksError(f"api.tarkov.dev 错误: {payload.get('errors')}")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("maps") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise TarkovKeyPacksError("tarkov.dev maps 门锁响应无效")
    return [row for row in rows if isinstance(row, dict)]


def maps_have_lock_data(maps: list[Any]) -> bool:
    """BOSS 精简包只有出生点，没有 locks / accessKeys，不能当门锁源。"""
    for row in maps:
        if not isinstance(row, dict):
            continue
        if row.get("locks") or row.get("accessKeys"):
            return True
    return False


def parse_json_maps_locks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """json.tarkov.dev maps：dict 按 id 索引，lock.key / accessKeys 多为物品 id 字符串。"""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    maps = data.get("maps") if isinstance(data, dict) else None
    if isinstance(maps, dict):
        raw_rows = [row for row in maps.values() if isinstance(row, dict)]
    elif isinstance(maps, list):
        raw_rows = [row for row in maps if isinstance(row, dict)]
    else:
        raise TarkovKeyPacksError("json.tarkov.dev maps 门锁响应无效")
    out: list[dict[str, Any]] = []
    for raw in raw_rows:
        slug = resolve_map_slug(str(raw.get("normalizedName") or raw.get("nameId") or ""))
        if not slug:
            continue
        out.append(
            {
                "name": MAP_ZH.get(slug) or str(raw.get("name") or ""),
                "normalizedName": slug,
                "locks": raw.get("locks") if isinstance(raw.get("locks"), list) else [],
                "accessKeys": (
                    raw.get("accessKeys") if isinstance(raw.get("accessKeys"), list) else []
                ),
            }
        )
    if not out:
        raise TarkovKeyPacksError("json.tarkov.dev maps 未解析到门锁")
    if not maps_have_lock_data(out):
        raise TarkovKeyPacksError("json.tarkov.dev maps 没有门锁")
    return out


def _decode_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovKeyPacksError(f"{label}解析失败") from exc
    if not isinstance(payload, dict):
        raise TarkovKeyPacksError(f"{label}格式无效")
    return payload


def _fetch_graphql_locks(*, lang: str) -> list[dict[str, Any]]:
    body = json.dumps(
        {
            "query": _LOCKS_QUERY,
            "variables": {"lang": lang, "gameMode": graphql_game_mode()},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    raw = _http_request(
        TARKOV_GRAPHQL_URL,
        method="POST",
        body=body,
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    maps = parse_locks_payload(_decode_json_object(raw, label="tarkov.dev maps 门锁"))
    if not maps_have_lock_data(maps):
        raise TarkovKeyPacksError("api.tarkov.dev maps 没有门锁")
    return maps


def _fetch_json_locks() -> list[dict[str, Any]]:
    raw = _http_request(json_resource_url("maps"), timeout=120)
    return parse_json_maps_locks(_decode_json_object(raw, label="json.tarkov.dev maps 门锁"))


def _locks_from_persisted(db: Session) -> list[dict[str, Any]] | None:
    from app.services.tarkov import upstream as upstream_svc

    payload = upstream_svc.load_raw(db, "maps")
    if not isinstance(payload, dict):
        return None
    try:
        maps = parse_json_maps_locks(payload)
    except TarkovKeyPacksError:
        logger.warning("key packs persisted maps dump has no locks")
        return None
    return maps


def fetch_map_locks(
    *,
    lang: str = "zh",
    db: Session | None = None,
) -> tuple[list[dict[str, Any]], str]:
    now = time.time()
    mode = parse_game_mode()
    key = _cache_key(mode)
    entry = _lock_cache.get(key) or {}
    cached = entry.get("maps")
    cached_source = str(entry.get("source") or SOURCE_GRAPHQL)
    if (
        isinstance(cached, list)
        and cached
        and maps_have_lock_data(cached)
        and now - float(entry.get("at") or 0) < _CACHE_TTL_SEC
    ):
        return cached, cached_source

    if db is not None:
        persisted = _locks_from_persisted(db)
        if persisted:
            _lock_cache[key] = {"at": now, "maps": persisted, "source": SOURCE_JSON}
            return persisted, SOURCE_JSON

    errors: list[str] = []
    try:
        maps = _fetch_graphql_locks(lang=lang)
        _lock_cache[key] = {"at": now, "maps": maps, "source": SOURCE_GRAPHQL}
        return maps, SOURCE_GRAPHQL
    except TarkovKeyPacksError as exc:
        errors.append(f"graphql: {exc}")
        logger.warning("key packs api.tarkov.dev locks failed: %s", exc)

    try:
        maps = _fetch_json_locks()
        _lock_cache[key] = {"at": now, "maps": maps, "source": SOURCE_JSON}
        return maps, SOURCE_JSON
    except TarkovKeyPacksError as exc:
        errors.append(f"json: {exc}")
        logger.warning("key packs json maps locks failed: %s", exc)

    if isinstance(cached, list) and cached:
        logger.warning("key packs using stale locks cache after: %s", "；".join(errors))
        return cached, SOURCE_STALE
    raise TarkovKeyPacksError(UNAVAILABLE_MSG)


def _catalog_rows(db: Session) -> tuple[list[dict[str, Any]], str | None, str | None]:
    try:
        _source, rows, synced_at, note = load_parsed_catalog(db)
        return rows, synced_at, note
    except TarkovItemsError as exc:
        logger.warning("key packs catalog unavailable: %s", exc)
        return [], None, None


def _guides_for_sources(db: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        _source, parsed, _synced, _note = load_parsed_guides(db)
        barters = parsed.get("barters") if isinstance(parsed.get("barters"), list) else []
        crafts = parsed.get("crafts") if isinstance(parsed.get("crafts"), list) else []
        return barters, crafts
    except TarkovGuidesError as exc:
        logger.warning("key packs guides unavailable: %s", exc)
        return [], []


def _tasks_for_keys(db: Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """任务 raw：奖励来源 + 所需钥匙。摘要行没有 neededKeys。"""
    locale: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    try:
        _source, rows, locale, _synced, _note = load_parsed_tasks(db)
    except TarkovTasksError as exc:
        logger.warning("key packs tasks unavailable: %s", exc)
        return [], {}
    names = {
        str(row.get("id") or ""): str(row.get("name") or "")
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }
    try:
        _src, payload, _synced, _note = tasks_svc._load_payload(db)
        locale = locale or tasks_svc._locale_map(payload)
        raw_rows: list[dict[str, Any]] = []
        for tid, row in tasks_svc._tasks_map(payload).items():
            if not isinstance(row, dict):
                continue
            copied = dict(row)
            task_id = str(copied.get("id") or tid).strip()
            copied["id"] = task_id
            parsed_name = names.get(task_id) or ""
            loc_name = tasks_svc._locale_lookup(
                locale, f"{task_id} name", f"{task_id} Name"
            )
            if parsed_name and not tasks_svc._is_placeholder_name(task_id, parsed_name):
                copied["name"] = parsed_name
            elif loc_name:
                copied["name"] = loc_name
            raw_rows.append(copied)
        return raw_rows, locale
    except TarkovTasksError as exc:
        logger.warning("key packs raw task rewards unavailable: %s", exc)
    return rows, locale


def _merge_note(catalog_note: str | None, source: str) -> str | None:
    extra = ""
    if source == SOURCE_JSON:
        extra = "门锁来自 json.tarkov.dev（api.tarkov.dev 暂不可用）"
    elif source == SOURCE_STALE:
        extra = "门锁为缓存（上游暂不可用）"
    if extra and catalog_note:
        return f"{catalog_note}；{extra}"
    return extra or catalog_note


def list_key_packs(db: Session) -> dict[str, Any]:
    maps, source = fetch_map_locks(lang="zh", db=db)
    catalog_rows, synced_at, note = _catalog_rows(db)
    grouped = group_key_packs(maps, catalog_rows)
    barters, crafts = _guides_for_sources(db)
    task_rows, locale = _tasks_for_keys(db)
    attach_key_sources(
        grouped,
        build_key_source_index(
            barters=barters,
            crafts=crafts,
            task_rows=task_rows,
            catalog_rows=catalog_rows,
        ),
    )
    attach_key_usage(grouped, build_key_usage_index(task_rows, locale=locale))
    return {
        **grouped,
        "source": source,
        "synced_at": synced_at,
        "note": _merge_note(note, source),
    }
