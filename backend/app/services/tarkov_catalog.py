"""从 items raw 解析通用手册物品目录与详情（不新建派生表）。

json.tarkov.dev 整包含 handbookCategories；GraphQL split 仅弹药/枪械。
目录接口在 raw 不是整包时会回源 json 一次，以便装备等分类有数据。
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.services import tarkov_items as items_svc
from app.services.tarkov_ammo import SOURCE_GRAPHQL, SOURCE_JSON_API
from app.services.tarkov_items import GRAPHQL_SPLIT_FORMAT, TarkovItemsError

logger = logging.getLogger(__name__)

CATALOG_PAGE_SIZE_DEFAULT = 50
CATALOG_PAGE_SIZE_MAX = 100

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
    name, short_name, _desc = _localized_name(item_id, raw, locale)
    types = raw.get("types") if isinstance(raw.get("types"), list) else []
    return {
        "id": item_id,
        "name": name,
        "short_name": short_name,
        "icon_link": str(
            raw.get("baseImageLink") or raw.get("iconLink") or ""
        ),
        "types": [str(t) for t in types if t is not None and str(t).strip()],
        "handbook_ids": _id_list(raw.get("handbookCategories")),
        "properties_type": str(props.get("propertiesType") or ""),
        "weight": _as_float(raw.get("weight")),
        "width": _as_int(raw.get("width")),
        "height": _as_int(raw.get("height")),
        "base_price": _as_int(raw.get("basePrice")),
        "avg24h_price": _as_int(raw.get("avg24hPrice")),
        "last_low_price": _as_int(raw.get("lastLowPrice")),
        "properties": _compact_properties(props) if isinstance(props, dict) else {},
    }


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
) -> dict[str, Any]:
    try:
        size = int(page_size)
    except (TypeError, ValueError):
        size = CATALOG_PAGE_SIZE_DEFAULT
    size = max(1, min(size, CATALOG_PAGE_SIZE_MAX))
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
    meta = items_svc.get_items_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    key = synced or ""
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
    key = synced_at or ""
    with _parsed_lock:
        _parsed_cache = (key, source, rows, synced_at, note)
    return source, rows, synced_at, note


def peek_catalog_items(db: Session) -> list[dict[str, Any]]:
    """搜索用：有 raw 则解析，不回源、不把 GraphQL split 升级成 json、不覆盖进程缓存。"""
    if items_svc.get_items_raw(db) is None:
        return []
    meta = items_svc.get_items_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    key = synced or ""
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
    for ident, raw in iter_raw_items(source, payload):
        if ident != item_id:
            continue
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
        return {
            "id": item_id,
            "name": name,
            "short_name": short_name,
            "description": description,
            "item": item_out,
            "properties": dict(props) if isinstance(props, dict) else {},
        }
    return None


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    items_svc.ensure_items(db)
    row = items_svc.get_items_raw(db)
    if row is None:
        raise TarkovItemsError("无物品 raw")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovItemsError("物品 raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovItemsError("物品 raw_json 格式无效")
    meta = items_svc.get_items_meta(db)
    synced = None
    if meta and meta.synced_at:
        synced = meta.synced_at.isoformat()
    note = (meta.note if meta else None) or row.note
    return row.source, payload, synced, note


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
    return detail
