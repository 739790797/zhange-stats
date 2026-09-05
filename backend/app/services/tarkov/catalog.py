"""从 items raw 解析通用手册物品目录与详情（不新建派生表）。

json.tarkov.dev 整包含 handbookCategories；GraphQL split 仅弹药/枪械。
目录接口在 raw 不是整包时会回源 json 一次，以便装备等分类有数据。
"""

from __future__ import annotations

import html
import logging
import re
import threading
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.services.tarkov import items as items_svc
from app.services.tarkov.ammo import SOURCE_GRAPHQL, SOURCE_JSON_API
from app.services.tarkov.overlay import parsed_cache_key
from app.services.tarkov.items import GRAPHQL_SPLIT_FORMAT, TarkovItemsError

logger = logging.getLogger(__name__)

CATALOG_PAGE_SIZE_DEFAULT = 50
CATALOG_PAGE_SIZE_MAX = 100

KEYS_HANDBOOK_IDS = {
    "5b47574386f77428ca22b342",
    "5c518ec986f7743b68682ce2",
    "5c518ed586f774119a772aee",
}
KEY_TYPES = {"key", "keys"}

# 列表不带槽位/预设等大对象；详情仍返回完整 properties。
_HEAVY_PROP_KEYS = {
    "slots",
    "presets",
    "ConflictingItems",
    "conflictingItems",
    "grid",
    "armorSlots",
    "content",
    "__typename",
}

_parsed_lock = threading.Lock()
_parsed_cache: tuple[
    str, str, list[dict[str, Any]], str | None, str | None
] | None = None
_pack_index_cache: tuple[str, dict[str, dict[str, Any]]] | None = None

# 手册「弹药 > 弹药包」
AMMO_PACK_HANDBOOK_ID = "5b47574386f77428ca22b33c"


def _id_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for key, val in value.items():
            if isinstance(val, dict):
                ident = val.get("id") or val.get("_id") or key
                if ident:
                    out.append(str(ident).strip())
            elif key:
                out.append(str(key).strip())
        return [x for x in out if x]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                ident = item.get("id") or item.get("_id")
                if ident:
                    out.append(str(ident).strip())
            elif item is not None and str(item).strip():
                out.append(str(item).strip())
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_ITEM_REF_KEYS = ("defaultAmmo", "defaultPreset", "baseItem")
_ITEM_REF_LIST_KEYS = ("allowedAmmo", "presets")
_BR_RE = re.compile(r"<br\s*/?>", re.I)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_GENERIC_CATEGORY_IDS = {
    "54009119af1c881c07000029",
    "566162e44bdc2d3f298b4573",
    "5661632d4bdc2d903d8b456b",
    "566168634bdc2d144c8b456c",
}


def _extract_ref_id(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("id") or value.get("_id") or "").strip()
    return ""


def _items_data_blob(payload: dict[str, Any]) -> dict[str, Any]:
    blob = payload.get("items")
    if not isinstance(blob, dict):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else None
        return data if isinstance(data, dict) else {}
    data = blob.get("data") if isinstance(blob.get("data"), dict) else blob
    return data if isinstance(data, dict) else {}


def _raw_items_by_id(source: str, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ident, raw in iter_raw_items(source, payload):
        if ident:
            out[ident] = raw
    return out


def _item_stub(
    item_id: str,
    raw: dict[str, Any] | None,
    locale: dict[str, Any],
) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {}
    name, short_name, _desc = _localized_name(item_id, row, locale)
    types = row.get("types") if isinstance(row.get("types"), list) else []
    return {
        "id": item_id,
        "name": name,
        "shortName": short_name,
        "types": [str(t) for t in types if t is not None and str(t).strip()],
        "iconLink": str(row.get("baseImageLink") or row.get("iconLink") or ""),
    }


def _resolve_item_ref(
    value: Any,
    items_by_id: dict[str, dict[str, Any]],
    locale: dict[str, Any],
) -> dict[str, Any] | None:
    ident = _extract_ref_id(value)
    if not ident:
        return None
    raw = items_by_id.get(ident)
    if not isinstance(raw, dict) and isinstance(value, dict):
        raw = value
    return _item_stub(ident, raw, locale)


def _localized_category_name(
    cat_id: str,
    locale: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> str:
    meta = meta if isinstance(meta, dict) else {}
    name = str(locale.get(f"{cat_id} Name") or locale.get(cat_id) or "").strip()
    placeholder = f"{cat_id} Name"
    if name and name not in {placeholder, cat_id}:
        return name
    raw_name = str(meta.get("name") or "").strip()
    if raw_name and raw_name not in {placeholder, cat_id}:
        return raw_name
    return str(meta.get("normalizedName") or cat_id)


def _resolve_category_list(
    value: Any,
    locale: dict[str, Any],
    catalogs: tuple[dict[str, Any], dict[str, Any]],
) -> list[dict[str, Any]]:
    item_cats, handbook_cats = catalogs
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cat_id in _id_list(value):
        if not cat_id or cat_id in seen or cat_id in _GENERIC_CATEGORY_IDS:
            continue
        seen.add(cat_id)
        meta = item_cats.get(cat_id) if isinstance(item_cats.get(cat_id), dict) else None
        if not isinstance(meta, dict):
            hb = handbook_cats.get(cat_id)
            meta = hb if isinstance(hb, dict) else {}
        name = _localized_category_name(cat_id, locale, meta)
        if not name or name == cat_id:
            continue
        out.append(
            {
                "id": cat_id,
                "name": name,
                "normalizedName": str(meta.get("normalizedName") or ""),
            }
        )
    return out


def _hydrate_ref_list(
    value: Any,
    items_by_id: dict[str, dict[str, Any]],
    locale: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_list = value if isinstance(value, list) else (
        [value] if value not in (None, "") else []
    )
    out: list[dict[str, Any]] = []
    for entry in raw_list:
        stub = _resolve_item_ref(entry, items_by_id, locale)
        if stub:
            out.append(stub)
    return out


def _plain_text_from_html(raw: str) -> str:
    text = _BR_RE.sub("\n", raw)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _hydrate_content(value: Any, locale: dict[str, Any]) -> list[str]:
    keys = value if isinstance(value, list) else []
    out: list[str] = []
    for key in keys:
        ident = str(key or "").strip()
        if not ident:
            continue
        loc = locale.get(ident)
        if not loc:
            continue
        text = _plain_text_from_html(str(loc))
        if text:
            out.append(text)
    return out


def _hydrate_contains_items(
    value: Any,
    items_by_id: dict[str, dict[str, Any]],
    locale: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, dict):
            ident = _extract_ref_id(entry.get("item") if "item" in entry else entry)
            count = entry.get("count") or 1
        else:
            ident = _extract_ref_id(entry)
            count = 1
        stub = _resolve_item_ref(ident, items_by_id, locale)
        if not stub:
            continue
        out.append({"item": stub, "count": count})
    return out


def _hydrate_armor_slots(
    slots: Any,
    items_by_id: dict[str, dict[str, Any]],
    locale: dict[str, Any],
) -> Any:
    if not isinstance(slots, list):
        return slots
    out: list[Any] = []
    for slot in slots:
        if not isinstance(slot, dict):
            out.append(slot)
            continue
        copied = dict(slot)
        plates = copied.get("allowedPlates")
        if isinstance(plates, list):
            resolved: list[dict[str, Any]] = []
            for entry in plates:
                stub = _resolve_item_ref(entry, items_by_id, locale)
                if stub:
                    resolved.append(stub)
            copied["allowedPlates"] = resolved
        out.append(copied)
    return out


def _hydrate_detail_refs(
    detail: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
    payload: dict[str, Any],
    locale: dict[str, Any],
) -> dict[str, Any]:
    """json.tarkov.dev 把弹药/预设/分类存成 id，详情需要名称才能展示。"""
    item = dict(detail.get("item") or {})
    props = dict(detail.get("properties") or {})
    data = _items_data_blob(payload)
    item_cats = data.get("itemCategories") if isinstance(data.get("itemCategories"), dict) else {}
    handbook_cats = (
        data.get("handbookCategories")
        if isinstance(data.get("handbookCategories"), dict)
        else {}
    )
    catalogs = (item_cats, handbook_cats)

    for key in _ITEM_REF_KEYS:
        if key not in props or props[key] in (None, ""):
            continue
        resolved = _resolve_item_ref(props[key], items_by_id, locale)
        if resolved:
            props[key] = resolved
    for key in _ITEM_REF_LIST_KEYS:
        if key not in props:
            continue
        props[key] = _hydrate_ref_list(props[key], items_by_id, locale)
    if "armorSlots" in props:
        props["armorSlots"] = _hydrate_armor_slots(
            props.get("armorSlots"), items_by_id, locale
        )
    if "content" in props:
        props["content"] = _hydrate_content(props.get("content"), locale)
    if "categories" in item:
        item["categories"] = _resolve_category_list(
            item.get("categories"), locale, catalogs
        )
    if "handbookCategories" in item:
        item["handbookCategories"] = _resolve_category_list(
            item.get("handbookCategories"), locale, catalogs
        )
    if "containsItems" in item:
        item["containsItems"] = _hydrate_contains_items(
            item.get("containsItems"), items_by_id, locale
        )
    if "conflictingItems" in item:
        item["conflictingItems"] = _hydrate_ref_list(
            item.get("conflictingItems"), items_by_id, locale
        )
    if "conflictingCategories" in item:
        item["conflictingCategories"] = _resolve_category_list(
            item.get("conflictingCategories"), locale, catalogs
        )
    detail["item"] = item
    detail["properties"] = props
    return detail


def _localized_name(
    item_id: str,
    raw: dict[str, Any],
    locale: dict[str, Any],
) -> tuple[str, str, str]:
    name = str(
        locale.get(f"{item_id} Name")
        or raw.get("name")
        or locale.get(f"{item_id} ShortName")
        or raw.get("shortName")
        or item_id
    )
    short_name = str(
        locale.get(f"{item_id} ShortName") or raw.get("shortName") or ""
    )
    description = str(
        locale.get(f"{item_id} Description") or raw.get("description") or ""
    )
    if description.endswith(" Description") and item_id in description:
        description = ""
    placeholder_name = f"{item_id} Name"
    if name == placeholder_name:
        name = short_name or item_id
    return name, short_name, description


def _compact_properties(props: dict[str, Any]) -> dict[str, Any]:
    """列表用属性：标量 / 简单数组 / grids 尺寸，去掉槽位树。"""
    out: dict[str, Any] = {}
    for key, value in props.items():
        if key in _HEAVY_PROP_KEYS:
            continue
        if key == "grids" and isinstance(value, list):
            grids: list[dict[str, Any]] = []
            for grid in value:
                if not isinstance(grid, dict):
                    continue
                width = _as_int(grid.get("width"))
                height = _as_int(grid.get("height"))
                if width is None or height is None:
                    continue
                grids.append({"width": width, "height": height})
            out[key] = grids
            continue
        if isinstance(value, dict):
            slim = {
                kk: value[kk]
                for kk in ("id", "name", "normalizedName")
                if kk in value and value[kk] not in (None, "")
            }
            if slim:
                out[key] = slim
            continue
        if isinstance(value, list):
            if value and all(not isinstance(x, (dict, list)) for x in value):
                out[key] = value
            continue
        out[key] = value
    return out


def _row_from_raw(
    item_id: str,
    raw: dict[str, Any],
    locale: dict[str, Any],
) -> dict[str, Any] | None:
    if not item_id:
        return None
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    name, short_name, description = _localized_name(item_id, raw, locale)
    types = raw.get("types") if isinstance(raw.get("types"), list) else []
    type_list = [str(t) for t in types if t is not None and str(t).strip()]
    handbook_ids = _id_list(raw.get("handbookCategories"))
    row = {
        "id": item_id,
        "name": name,
        "short_name": short_name,
        "icon_link": str(
            raw.get("baseImageLink") or raw.get("iconLink") or ""
        ),
        "types": type_list,
        "handbook_ids": handbook_ids,
        "properties_type": str(props.get("propertiesType") or ""),
        "weight": _as_float(raw.get("weight")),
        "width": _as_int(raw.get("width")),
        "height": _as_int(raw.get("height")),
        "base_price": _as_int(raw.get("basePrice")),
        "avg24h_price": _as_int(raw.get("avg24hPrice")),
        "last_low_price": _as_int(raw.get("lastLowPrice")),
        "properties": _compact_properties(props) if isinstance(props, dict) else {},
    }
    if description and _is_handbook_key(handbook_ids, type_list):
        row["description"] = description
    return row


def _is_handbook_key(handbook_ids: list[str], types: list[str]) -> bool:
    handbook = {str(x) for x in handbook_ids if x}
    type_set = {str(x).strip().lower() for x in types if x}
    return bool(handbook & KEYS_HANDBOOK_IDS) or bool(type_set & KEY_TYPES)


def _iter_json_items(
    payload: dict[str, Any],
) -> Iterable[tuple[str, dict[str, Any]]]:
    items = items_svc._json_items_map(payload)
    for item_id, raw in items.items():
        if isinstance(raw, dict):
            ident = str(raw.get("id") or item_id).strip()
            yield ident, raw


def _iter_graphql_split_items(
    payload: dict[str, Any],
) -> Iterable[tuple[str, dict[str, Any]]]:
    ammo_payload = payload.get("ammo")
    if isinstance(ammo_payload, dict):
        data = ammo_payload.get("data") if isinstance(ammo_payload.get("data"), dict) else {}
        rows = data.get("ammo") if isinstance(data, dict) else None
        if isinstance(rows, list):
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                item = raw.get("item") if isinstance(raw.get("item"), dict) else {}
                item_id = str(item.get("id") or "").strip()
                if not item_id:
                    continue
                props = {k: v for k, v in raw.items() if k != "item" and v is not None}
                merged = dict(item)
                merged["properties"] = props
                yield item_id, merged

    guns_payload = payload.get("guns")
    if isinstance(guns_payload, dict):
        data = guns_payload.get("data") if isinstance(guns_payload.get("data"), dict) else {}
        rows = data.get("items") if isinstance(data, dict) else None
        if isinstance(rows, list):
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                item_id = str(raw.get("id") or "").strip()
                if item_id:
                    yield item_id, raw


def iter_raw_items(
    source: str,
    payload: dict[str, Any],
) -> Iterable[tuple[str, dict[str, Any]]]:
    src = (source or "").strip()
    if src == SOURCE_GRAPHQL and payload.get("format") == GRAPHQL_SPLIT_FORMAT:
        yield from _iter_graphql_split_items(payload)
        return
    yield from _iter_json_items(payload)


def payload_has_full_items(source: str, payload: dict[str, Any]) -> bool:
    src = (source or "").strip()
    if src == SOURCE_GRAPHQL and payload.get("format") == GRAPHQL_SPLIT_FORMAT:
        return False
    return bool(items_svc._json_items_map(payload))


def _is_ammo_pack(raw: dict[str, Any]) -> bool:
    types = raw.get("types") if isinstance(raw.get("types"), list) else []
    if any(str(t).strip() == "ammoBox" for t in types):
        return True
    handbook = set(_id_list(raw.get("handbookCategories")))
    if AMMO_PACK_HANDBOOK_ID in handbook:
        return True
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    return str(props.get("propertiesType") or "") == "ItemPropertiesAmmoBox"


def _contained_ammo_entries(raw: dict[str, Any]) -> list[tuple[str, int]]:
    blobs: list[Any] = []
    if isinstance(raw.get("containsItems"), list):
        blobs.append(raw.get("containsItems"))
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    if isinstance(props.get("containsItems"), list):
        blobs.append(props.get("containsItems"))
    out: list[tuple[str, int]] = []
    seen: set[str] = set()
    for contains in blobs:
        if not isinstance(contains, list):
            continue
        for entry in contains:
            if isinstance(entry, dict):
                ident = _extract_ref_id(entry.get("item") if "item" in entry else entry)
                try:
                    count = int(entry.get("count") or 1)
                except (TypeError, ValueError):
                    count = 1
            else:
                ident = _extract_ref_id(entry)
                count = 1
            if not ident or ident in seen:
                continue
            seen.add(ident)
            out.append((ident, max(count, 1)))
    return out


def parse_ammo_pack_index(
    source: str, payload: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """子弹 id → 对应弹药包（多包时取发数最多的）。"""
    index: dict[str, dict[str, Any]] = {}
    for item_id, raw in iter_raw_items(source, payload):
        if not item_id or not isinstance(raw, dict) or not _is_ammo_pack(raw):
            continue
        icon = str(raw.get("baseImageLink") or raw.get("iconLink") or "").strip()[:512]
        for ammo_id, count in _contained_ammo_entries(raw):
            prev = index.get(ammo_id)
            better = prev is None or count > int(prev.get("pack_count") or 0)
            if not better and prev is not None and count == int(prev.get("pack_count") or 0):
                better = bool(icon) and not str(prev.get("pack_icon_link") or "")
            if not better:
                continue
            index[ammo_id] = {
                "pack_item_id": item_id,
                "pack_icon_link": icon,
                "pack_count": count,
            }
    return index


def list_ammo_pack_index(db: Session) -> dict[str, dict[str, Any]]:
    """当前模式 items raw 里的弹药包索引；缺 raw / 解析失败时为空。"""
    global _pack_index_cache
    if items_svc.get_items_raw(db) is None:
        return {}
    _source, synced, _note = items_svc.items_raw_header(db)
    key = parsed_cache_key(db, synced)
    with _parsed_lock:
        cached = _pack_index_cache
        if cached is not None and cached[0] == key:
            return cached[1]
    try:
        source, payload, synced_at, _note = _load_payload(db)
    except TarkovItemsError:
        return {}
    index = parse_ammo_pack_index(source, payload)
    key = parsed_cache_key(db, synced_at)
    with _parsed_lock:
        _pack_index_cache = (key, index)
    return index


def parse_catalog_items(source: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    locale = items_svc._locale_map(payload)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item_id, raw in iter_raw_items(source, payload):
        if item_id in seen:
            continue
        row = _row_from_raw(item_id, raw, locale)
        if not row:
            continue
        seen.add(item_id)
        rows.append(row)
    rows.sort(key=lambda r: (str(r.get("name") or ""), str(r.get("id") or "")))
    return rows


# tarkov.dev ItemType 旧名 / 别名 → 目录里实际写入的 types
_TYPE_ALIASES = {
    "silencer": "suppressor",
    "headset": "headphones",
}


def _expand_types(types: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for raw in types:
        key = str(raw or "").strip()
        if not key:
            continue
        out.add(key)
        alias = _TYPE_ALIASES.get(key)
        if alias:
            out.add(alias)
        for src, dst in _TYPE_ALIASES.items():
            if key == dst:
                out.add(src)
    return out


def filter_catalog_items(
    rows: list[dict[str, Any]],
    *,
    category_ids: list[str] | None = None,
    types: list[str] | None = None,
) -> list[dict[str, Any]]:
    cats = {c.strip() for c in (category_ids or []) if c and c.strip()}
    type_set = _expand_types(str(t) for t in (types or []) if t is not None)
    if not cats and not type_set:
        return list(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        handbook = set(row.get("handbook_ids") or [])
        row_types = set(row.get("types") or [])
        hit_cat = bool(cats) and bool(handbook & cats)
        hit_type = bool(type_set) and bool(row_types & type_set)
        if cats and type_set:
            if hit_cat or hit_type:
                out.append(row)
        elif cats:
            if hit_cat:
                out.append(row)
        elif hit_type:
            out.append(row)
    return out


def search_catalog_items(
    rows: list[dict[str, Any]],
    q: str | None,
) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    if not needle:
        return list(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").lower()
        short_name = str(row.get("short_name") or "").lower()
        item_id = str(row.get("id") or "").lower()
        if needle in name or needle in short_name or needle in item_id:
            out.append(row)
    return out


def paginate_catalog_items(
    rows: list[dict[str, Any]],
    *,
    page: int = 1,
    page_size: int = CATALOG_PAGE_SIZE_DEFAULT,
    max_size: int = CATALOG_PAGE_SIZE_MAX,
) -> dict[str, Any]:
    try:
        size = int(page_size)
    except (TypeError, ValueError):
        size = CATALOG_PAGE_SIZE_DEFAULT
    size = max(1, min(size, max_size))
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
        "item_count": total,
        "page": page_n,
        "page_size": size,
    }


def load_parsed_catalog(
    db: Session,
) -> tuple[str, list[dict[str, Any]], str | None, str | None]:
    """解析整包目录；synced_at 未变则复用进程缓存，翻页不必重读 raw_json。"""
    global _parsed_cache
    items_svc.ensure_items(db)
    _source, synced, _note = items_svc.items_raw_header(db)
    key = parsed_cache_key(db, synced)
    with _parsed_lock:
        cached = _parsed_cache
        if cached is not None and cached[0] == key:
            return cached[1], cached[2], cached[3], cached[4]

    source, payload, synced_at, note = _load_payload(db)
    if not payload_has_full_items(source, payload):
        try:
            ensure_full_item_catalog(db)
            source, payload, synced_at, note = _load_payload(db)
        except TarkovItemsError as exc:
            logger.warning("upgrade catalog to json failed, using split raw: %s", exc)
    rows = parse_catalog_items(source, payload)
    key = parsed_cache_key(db, synced_at)
    with _parsed_lock:
        _parsed_cache = (key, source, rows, synced_at, note)
    return source, rows, synced_at, note


def peek_catalog_items(db: Session) -> list[dict[str, Any]]:
    """搜索用：有 raw 则解析，不回源、不把 GraphQL split 升级成 json、不覆盖进程缓存。"""
    if items_svc.get_items_raw(db) is None:
        return []
    _source, synced, _note = items_svc.items_raw_header(db)
    key = parsed_cache_key(db, synced)
    with _parsed_lock:
        cached = _parsed_cache
        if cached is not None and cached[0] == key:
            return list(cached[2])
    source, payload, _synced, _note = _load_payload(db)
    return parse_catalog_items(source, payload)


def extract_item_detail(
    source: str,
    payload: dict[str, Any],
    item_id: str,
) -> dict[str, Any] | None:
    item_id = (item_id or "").strip()
    if not item_id:
        return None
    locale = items_svc._locale_map(payload)
    items_by_id = _raw_items_by_id(source, payload)
    raw = items_by_id.get(item_id)
    if not isinstance(raw, dict):
        return None
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    name, short_name, description = _localized_name(item_id, raw, locale)
    item_out = {k: v for k, v in raw.items() if k != "properties"}
    item_out["name"] = name
    item_out["shortName"] = short_name
    if description:
        item_out["description"] = description
    elif "description" in item_out and str(item_out["description"]).endswith(
        " Description"
    ):
        item_out.pop("description", None)
    detail = {
        "id": item_id,
        "name": name,
        "short_name": short_name,
        "description": description,
        "item": item_out,
        "properties": dict(props) if isinstance(props, dict) else {},
    }
    return _hydrate_detail_refs(detail, items_by_id, payload, locale)


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    from app.services.tarkov import overlay as overlay_svc
    from app.services.tarkov import upstream as upstream_svc

    items_svc.ensure_items(db)
    source, payload, synced, note = upstream_svc.load_main_payload(
        db,
        "items",
        error_cls=TarkovItemsError,
        missing="无物品 raw",
        invalid="物品 raw_json 无效",
    )
    return source, overlay_svc.apply_loaded_overlay(db, "items", payload), synced, note


def ensure_full_item_catalog(db: Session) -> None:
    """目录需要整包 items；若当前是 GraphQL split 则回源 json 一次。"""
    source, payload, _synced, _note = _load_payload(db)
    if payload_has_full_items(source, payload):
        return
    logger.info("tarkov catalog needs json items; upgrading raw from GraphQL split")
    bundle = items_svc.download_json_api_items(lang="zh")
    items_svc.persist_items_bundle(db, bundle)


def list_catalog(
    db: Session,
    *,
    category_ids: list[str] | None = None,
    types: list[str] | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = CATALOG_PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    cats = [c.strip() for c in (category_ids or []) if c and c.strip()]
    type_filters = [t.strip() for t in (types or []) if t and t.strip()]
    if not cats and not type_filters:
        raise TarkovItemsError("请指定 category_ids 或 types")

    source, all_rows, synced_at, note = load_parsed_catalog(db)
    rows = search_catalog_items(
        filter_catalog_items(
            all_rows,
            category_ids=cats,
            types=type_filters,
        ),
        q,
    )
    paged = paginate_catalog_items(rows, page=page, page_size=page_size)
    return {
        "items": paged["items"],
        "item_count": paged["item_count"],
        "page": paged["page"],
        "page_size": paged["page_size"],
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def list_loot_tiers(
    db: Session,
    *,
    q: str | None = None,
    tier: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """对齐 tarkov.dev loot-tiers：按跳蚤每格价排序。"""
    source, all_rows, synced_at, note = load_parsed_catalog(db)
    needle = (q or "").strip().lower()
    tier_key = (tier or "").strip().upper()
    ranked: list[dict[str, Any]] = []
    for row in all_rows:
        types = {str(t).lower() for t in (row.get("types") or [])}
        if "preset" in types or "quest" in types:
            continue
        width = int(row.get("width") or 1)
        height = int(row.get("height") or 1)
        slots = max(width * height, 1)
        price = row.get("last_low_price")
        if not isinstance(price, int) or price <= 0:
            price = row.get("avg24h_price")
        if not isinstance(price, int) or price <= 0:
            continue
        pps = int(price / slots)
        name = str(row.get("name") or "")
        if needle and needle not in name.lower() and needle not in str(row.get("id") or "").lower():
            continue
        if pps >= 40000:
            band = "S"
        elif pps >= 25000:
            band = "A"
        elif pps >= 15000:
            band = "B"
        elif pps >= 8000:
            band = "C"
        elif pps >= 4000:
            band = "D"
        else:
            band = "E"
        if tier_key and band != tier_key:
            continue
        ranked.append(
            {
                "id": row.get("id") or "",
                "name": name,
                "short_name": row.get("short_name") or "",
                "icon_link": row.get("icon_link") or "",
                "types": row.get("types") or [],
                "width": width,
                "height": height,
                "slots": slots,
                "price": price,
                "price_per_slot": pps,
                "tier": band,
            }
        )
    ranked.sort(key=lambda r: (-int(r.get("price_per_slot") or 0), str(r.get("name") or "")))
    paged = paginate_catalog_items(
        ranked, page=page, page_size=page_size, max_size=200
    )
    return {
        "items": paged["items"],
        "item_count": paged["item_count"],
        "page": paged["page"],
        "page_size": paged["page_size"],
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def _detail_is_key(detail: dict[str, Any]) -> bool:
    item = detail.get("item") if isinstance(detail.get("item"), dict) else {}
    types = [str(t) for t in (item.get("types") or []) if t]
    return _is_handbook_key(_id_list(item.get("handbookCategories")), types)


def attach_item_key_locks(db: Session, detail: dict[str, Any]) -> None:
    """钥匙详情反查 dump 门锁；地图 raw 缺失时保持空列表，不挡物品页。"""
    detail["locks"] = []
    if not _detail_is_key(detail):
        return
    try:
        from app.services.tarkov.bosses import (
            _load_payload as load_maps_payload,
            ensure_maps,
            get_maps_raw,
        )
        from app.services.tarkov.maps import collect_key_lock_maps

        if get_maps_raw(db) is None:
            ensure_maps(db)
        _source, maps_payload, _synced, _note = load_maps_payload(db)
        detail["locks"] = collect_key_lock_maps(
            maps_payload, str(detail.get("id") or "")
        )
    except Exception:  # noqa: BLE001
        logger.warning("item key locks unavailable", exc_info=True)


def get_item_detail(db: Session, item_id: str) -> dict[str, Any]:
    item_id = (item_id or "").strip()
    if not item_id:
        raise TarkovItemsError("物品 id 无效")

    source, payload, _synced, _note = _load_payload(db)
    detail = extract_item_detail(source, payload, item_id)
    if detail is None and not payload_has_full_items(source, payload):
        try:
            ensure_full_item_catalog(db)
            source, payload, _synced, _note = _load_payload(db)
            detail = extract_item_detail(source, payload, item_id)
        except TarkovItemsError as exc:
            logger.warning("upgrade catalog for detail failed: %s", exc)
    if detail is None:
        raise TarkovItemsError(f"未找到物品: {item_id}")
    detail["source"] = source
    attach_item_key_locks(db, detail)
    return detail
