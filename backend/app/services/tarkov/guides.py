"""逃离塔科夫藏身处 / 以物易物 / 制作：json.tarkov.dev raw → 列表投影。"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovHideoutRaw
from app.services.tarkov.ammo import SOURCE_JSON_API
from app.services.tarkov.game_mode import (
    json_api_prefix,
    json_resource_url,
    parse_game_mode,
    run_for_modes,
)
from app.services.tarkov.overlay import parsed_cache_key
from app.services.tarkov.http import download_bytes
from app.services.tarkov.tasks import TRADER_BY_ID

logger = logging.getLogger(__name__)

GUIDES_JOB_KEY = "tarkov_guides_sync"
DOWNLOAD_TIMEOUT = 180
PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 100

TARKOV_JSON_HIDEOUT_URL = "https://json.tarkov.dev/regular/hideout"
TARKOV_JSON_HIDEOUT_LOCALE_URL = "https://json.tarkov.dev/regular/hideout_{lang}"
TARKOV_JSON_BARTERS_URL = "https://json.tarkov.dev/regular/barters"
TARKOV_JSON_CRAFTS_URL = "https://json.tarkov.dev/regular/crafts"

_parsed_lock = threading.Lock()
_parsed_cache: tuple[str, dict[str, Any]] | None = None


class TarkovGuidesError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class GuidesUpstreamBundle:
    source: str
    payload: dict[str, Any]
    note: str


def _http_request(
    url: str,
    *,
    timeout: int = DOWNLOAD_TIMEOUT,
) -> bytes:
    return download_bytes(url, timeout=timeout, error_cls=TarkovGuidesError)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _id_of(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("id") or "").strip()
    return str(raw or "").strip()


def _locale_lookup(locale: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if not key:
            continue
        val = locale.get(key)
        if val is not None and str(val).strip():
            text = str(val).strip()
            if text.endswith(" Name") and key in text:
                continue
            return text
    return ""


def _json_data(payload: dict[str, Any]) -> Any:
    data = payload.get("data")
    if data is not None:
        return data
    return payload


def _download_json(url: str) -> dict[str, Any]:
    raw = _http_request(url)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovGuidesError(f"解析失败: {url}") from exc
    if not isinstance(payload, dict):
        raise TarkovGuidesError(f"格式无效: {url}")
    return payload


def download_json_guides(*, lang: str = "zh") -> GuidesUpstreamBundle:
    hideout_payload = _download_json(json_resource_url("hideout"))
    hideout = hideout_payload.get("data")
    if not isinstance(hideout, dict) or not hideout:
        raise TarkovGuidesError("json.tarkov.dev hideout 为空")

    locale: dict[str, Any] = {}
    try:
        loc_payload = _download_json(json_resource_url("hideout", lang=lang))
        loc_data = loc_payload.get("data")
        if isinstance(loc_data, dict):
            locale = loc_data
    except TarkovGuidesError:
        logger.warning("json.tarkov.dev hideout_%s locale unavailable", lang)

    barters_payload = _download_json(json_resource_url("barters"))
    barters = barters_payload.get("data")
    if not isinstance(barters, list):
        raise TarkovGuidesError("json.tarkov.dev barters 格式无效")

    crafts_payload = _download_json(json_resource_url("crafts"))
    crafts = crafts_payload.get("data")
    if not isinstance(crafts, list):
        raise TarkovGuidesError("json.tarkov.dev crafts 格式无效")

    return GuidesUpstreamBundle(
        source=SOURCE_JSON_API,
        payload={
            "hideout": hideout,
            "barters": barters,
            "crafts": crafts,
            "locale": locale,
        },
        note=f"json.tarkov.dev/{json_api_prefix()}/hideout+barters+crafts",
    )


def _item_req(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    item_id = _id_of(raw.get("item"))
    if not item_id:
        return None
    count = _as_float(raw.get("count"), 1) or 1
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    return {
        "id": item_id,
        "count": int(count) if count == int(count) else count,
        "found_in_raid": bool(attrs.get("foundInRaid")),
    }


def parse_hideout_stations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locale = payload.get("locale") if isinstance(payload.get("locale"), dict) else {}
    blob = payload.get("hideout")
    if not isinstance(blob, dict):
        return []
    rows: list[dict[str, Any]] = []
    for ident, raw in blob.items():
        if not isinstance(raw, dict):
            continue
        slug = str(raw.get("normalizedName") or "").strip()
        name_key = str(raw.get("name") or "")
        name = _locale_lookup(locale, name_key, slug) or slug or ident
        levels: list[dict[str, Any]] = []
        for level in raw.get("levels") or []:
            if not isinstance(level, dict):
                continue
            item_reqs = [
                req
                for req in (_item_req(x) for x in (level.get("itemRequirements") or []))
                if req
            ]
            station_reqs: list[dict[str, Any]] = []
            for req in level.get("stationLevelRequirements") or []:
                if not isinstance(req, dict):
                    continue
                station_id = _id_of(req.get("station"))
                if not station_id:
                    continue
                station_reqs.append(
                    {
                        "station_id": station_id,
                        "level": _as_int(req.get("level"), 0),
                    }
                )
            trader_reqs: list[dict[str, Any]] = []
            for req in level.get("traderRequirements") or []:
                if not isinstance(req, dict):
                    continue
                trader_id = _id_of(req.get("trader"))
                slug_t, tname = TRADER_BY_ID.get(trader_id, ("", trader_id))
                trader_reqs.append(
                    {
                        "id": trader_id,
                        "slug": slug_t,
                        "name": tname.split("（", 1)[0] if tname else slug_t,
                        "level": _as_int(req.get("level") or req.get("value"), 0),
                    }
                )
            skill_reqs: list[dict[str, Any]] = []
            for req in level.get("skillRequirements") or []:
                if not isinstance(req, dict):
                    continue
                skill_key = str(req.get("skill") or "")
                skill_reqs.append(
                    {
                        "skill": _locale_lookup(locale, skill_key) or skill_key,
                        "level": _as_int(req.get("level"), 0),
                    }
                )
            desc_key = str(level.get("description") or "")
            levels.append(
                {
                    "id": str(level.get("id") or ""),
                    "level": _as_int(level.get("level"), 0),
                    "construction_time": _as_int(level.get("constructionTime"), 0),
                    "description": _locale_lookup(locale, desc_key) or "",
                    "item_requirements": item_reqs,
                    "station_requirements": station_reqs,
                    "trader_requirements": trader_reqs,
                    "skill_requirements": skill_reqs,
                }
            )
        levels.sort(key=lambda r: int(r.get("level") or 0))
        rows.append(
            {
                "id": str(raw.get("id") or ident),
                "slug": slug or ident,
                "name": name,
                "image_link": str(raw.get("imageLink") or ""),
                "level_count": len(levels),
                "levels": levels,
            }
        )
    rows.sort(key=lambda r: str(r.get("name") or ""))
    by_id = {str(r.get("id") or ""): r for r in rows}

    def fill_station_names(row: dict[str, Any]) -> None:
        for level in row.get("levels") or []:
            for req in level.get("station_requirements") or []:
                other = by_id.get(str(req.get("station_id") or ""))
                req["station_slug"] = (other or {}).get("slug") or ""
                req["station_name"] = (other or {}).get("name") or req.get("station_id")

    for row in rows:
        fill_station_names(row)
    return rows


def parse_barters(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blob = payload.get("barters")
    if not isinstance(blob, list):
        return []
    rows: list[dict[str, Any]] = []
    for raw in blob:
        if not isinstance(raw, dict):
            continue
        trader_id = _id_of(raw.get("trader"))
        slug, tname = TRADER_BY_ID.get(trader_id, ("", trader_id))
        required = [
            req
            for req in (_item_req(x) for x in (raw.get("requiredItems") or []))
            if req
        ]
        offered = _item_req(raw.get("offeredItem")) or {}
        if not offered.get("id"):
            continue
        rows.append(
            {
                "id": str(raw.get("id") or ""),
                "trader_id": trader_id,
                "trader_slug": slug,
                "trader_name": tname.split("（", 1)[0] if tname else slug or trader_id,
                "min_trader_level": _as_int(raw.get("minTraderLevel"), 0),
                "task_unlock": _id_of(raw.get("taskUnlock")) or None,
                "required_items": required,
                "offered_item": offered,
            }
        )
    return rows


def parse_crafts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blob = payload.get("crafts")
    if not isinstance(blob, list):
        return []
    stations = {
        str(s.get("id") or ""): s
        for s in parse_hideout_stations(payload)
    }
    rows: list[dict[str, Any]] = []
    for raw in blob:
        if not isinstance(raw, dict):
            continue
        station_id = _id_of(raw.get("station"))
        station = stations.get(station_id) or {}
        required = [
            req
            for req in (_item_req(x) for x in (raw.get("requiredItems") or []))
            if req
        ]
        product = _item_req(raw.get("productItem")) or {}
        if not product.get("id"):
            continue
        rows.append(
            {
                "id": str(raw.get("id") or ""),
                "station_id": station_id,
                "station_slug": station.get("slug") or "",
                "station_name": station.get("name") or station_id,
                "level": _as_int(raw.get("level"), 0),
                "duration": _as_int(raw.get("duration"), 0),
                "required_items": required,
                "product_item": product,
            }
        )
    rows.sort(
        key=lambda r: (
            str(r.get("station_name") or ""),
            int(r.get("level") or 0),
            str(r.get("id") or ""),
        )
    )
    return rows


def get_hideout_raw(db: Session) -> TarkovHideoutRaw | None:
    from app.services.tarkov import upstream as upstream_svc

    return upstream_svc.load_raw_row(db, "hideout")


def guides_cache_token(db: Session) -> str:
    """hideout / barters / crafts 三份 raw 的 synced_at，给图鉴 ETag。"""
    from app.services.tarkov import upstream as upstream_svc

    parts: list[str] = []
    for resource in ("hideout", "barters", "crafts"):
        _source, synced, _note = upstream_svc.raw_row_header(
            upstream_svc.load_raw_row(db, resource)
        )
        parts.append(synced or "")
    return "|".join(parts)


def assemble_guides_envelope(
    hideout_payload: dict[str, Any],
    *,
    barters_payload: dict[str, Any] | None = None,
    crafts_payload: dict[str, Any] | None = None,
    locale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """三张 raw 表 / dump 文件 → parse 用的 {hideout, barters, crafts, locale}。"""
    unwrapped = _unwrap_part(hideout_payload)
    if (
        isinstance(unwrapped, dict)
        and isinstance(unwrapped.get("hideout"), dict)
        and (
            isinstance(unwrapped.get("barters"), list)
            or isinstance(unwrapped.get("crafts"), list)
        )
    ):
        envelope = {
            "hideout": unwrapped["hideout"],
            "barters": unwrapped["barters"] if isinstance(unwrapped.get("barters"), list) else [],
            "crafts": unwrapped["crafts"] if isinstance(unwrapped.get("crafts"), list) else [],
            "locale": unwrapped["locale"] if isinstance(unwrapped.get("locale"), dict) else {},
        }
    else:
        hideout = unwrapped if isinstance(unwrapped, dict) else {}
        barters = _unwrap_part(barters_payload) if isinstance(barters_payload, dict) else None
        crafts = _unwrap_part(crafts_payload) if isinstance(crafts_payload, dict) else None
        envelope = {
            "hideout": hideout,
            "barters": barters if isinstance(barters, list) else [],
            "crafts": crafts if isinstance(crafts, list) else [],
            "locale": {},
        }
    if locale:
        envelope["locale"] = locale
    return envelope


def persist_guides_bundle(db: Session, bundle: GuidesUpstreamBundle) -> dict[str, Any]:
    from app.services.tarkov import upstream as upstream_svc

    global _parsed_cache
    stations = parse_hideout_stations(bundle.payload)
    barters = parse_barters(bundle.payload)
    crafts = parse_crafts(bundle.payload)
    if not stations:
        raise TarkovGuidesError("未解析到藏身处数据")
    now = now_naive()
    hideout = bundle.payload.get("hideout")
    if not isinstance(hideout, dict):
        hideout = upstream_svc.unwrap_json_blob(bundle.payload)
    if not isinstance(hideout, dict):
        raise TarkovGuidesError("未解析到藏身处数据")
    persist_barters = bundle.payload.get("barters")
    persist_crafts = bundle.payload.get("crafts")
    upstream_svc.persist_raw(
        db,
        "hideout",
        hideout if "data" in hideout else {"data": hideout},
        source=bundle.source,
        note=bundle.note,
        commit=False,
    )
    if isinstance(persist_barters, list):
        upstream_svc.persist_raw(
            db,
            "barters",
            {"data": persist_barters},
            source=bundle.source,
            note=bundle.note,
            commit=False,
        )
    elif isinstance(persist_barters, dict):
        upstream_svc.persist_raw(
            db,
            "barters",
            persist_barters,
            source=bundle.source,
            note=bundle.note,
            commit=False,
        )
    if isinstance(persist_crafts, list):
        upstream_svc.persist_raw(
            db,
            "crafts",
            {"data": persist_crafts},
            source=bundle.source,
            note=bundle.note,
            commit=False,
        )
    elif isinstance(persist_crafts, dict):
        upstream_svc.persist_raw(
            db,
            "crafts",
            persist_crafts,
            source=bundle.source,
            note=bundle.note,
            commit=False,
        )
    upstream_svc.persist_locale_if_present(
        db,
        "hideout",
        bundle.payload,
        source=bundle.source,
        note=bundle.note,
    )
    db.commit()
    with _parsed_lock:
        _parsed_cache = None
    return {
        "station_count": len(stations),
        "barter_count": len(barters),
        "craft_count": len(crafts),
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
        "note": bundle.note,
    }


def _sync_current_mode(db: Session) -> dict[str, Any]:
    logger.info(
        "syncing tarkov hideout/barters/crafts from upstream (%s)",
        parse_game_mode(),
    )
    return persist_guides_bundle(db, download_json_guides(lang="zh"))


def sync_from_upstream(db: Session, *, game_mode: str | None = None) -> dict[str, Any]:
    return run_for_modes(
        lambda: _sync_current_mode(db),
        game_mode=game_mode,
        error_cls=TarkovGuidesError,
        label="藏身处",
    )


def _unwrap_part(blob: dict[str, Any] | None) -> Any:
    from app.services.tarkov import upstream as upstream_svc

    if not isinstance(blob, dict):
        return None
    return upstream_svc.unwrap_json_blob(blob)


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    from app.services.tarkov import overlay as overlay_svc
    from app.services.tarkov import upstream as upstream_svc

    source, payload, synced, note = upstream_svc.load_main_payload(
        db,
        "hideout",
        error_cls=TarkovGuidesError,
        missing="无藏身处 / 交换 raw",
        invalid="藏身处 raw_json 无效",
    )
    envelope = assemble_guides_envelope(
        payload,
        barters_payload=upstream_svc.load_raw(db, "barters"),
        crafts_payload=upstream_svc.load_raw(db, "crafts"),
        locale=payload.get("locale") if isinstance(payload.get("locale"), dict) else None,
    )
    if not envelope.get("locale"):
        envelope["locale"] = upstream_svc.load_locale_map(db, "hideout", payload=payload)
    envelope = overlay_svc.apply_loaded_overlay(db, "crafts", envelope)
    return source, envelope, synced, note


def load_parsed_guides(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    global _parsed_cache
    row = get_hideout_raw(db)
    synced = row.synced_at.isoformat() if row and row.synced_at else None
    key = parsed_cache_key(db, synced)
    with _parsed_lock:
        cached = _parsed_cache
        if cached is not None and cached[0] == key:
            source, _payload, synced_at, note = _load_payload(db)
            return source, cached[1], synced_at, note
    source, payload, synced_at, note = _load_payload(db)
    parsed = {
        "stations": parse_hideout_stations(payload),
        "barters": parse_barters(payload),
        "crafts": parse_crafts(payload),
    }
    with _parsed_lock:
        _parsed_cache = (key, parsed)
    return source, parsed, synced_at, note


def ensure_guides(db: Session) -> None:
    if get_hideout_raw(db) is None:
        sync_from_upstream(db, game_mode=parse_game_mode())


def _lookup_items(db: Session, item_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not item_ids:
        return {}
    try:
        from app.services.tarkov import catalog as catalog_svc
        from app.services.tarkov import items as items_svc

        source, payload, _synced, _note = catalog_svc._load_payload(db)
        if not catalog_svc.payload_has_full_items(source, payload):
            return {}
        locale = items_svc._locale_map(payload)
        out: dict[str, dict[str, Any]] = {}
        for ident, raw in catalog_svc.iter_raw_items(source, payload):
            if ident not in item_ids:
                continue
            row = catalog_svc._row_from_raw(ident, raw, locale)
            if row:
                out[ident] = row
        return out
    except Exception:  # noqa: BLE001
        logger.warning("guides item lookup failed", exc_info=True)
        return {}


def _enrich_item(req: dict[str, Any], items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item_id = str(req.get("id") or "")
    found = items.get(item_id) or {}
    return {
        "id": item_id,
        "name": found.get("name") or item_id,
        "short_name": found.get("short_name") or "",
        "icon_link": found.get("icon_link") or "",
        "types": found.get("types") or [],
        "count": req.get("count") or 1,
        "found_in_raid": bool(req.get("found_in_raid")),
        "flea_price": found.get("last_low_price") or found.get("avg24h_price"),
    }


def _collect_ids(*groups: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for group in groups:
        for row in group:
            ident = str(row.get("id") or "")
            if ident:
                out.add(ident)
    return out


def list_hideout(db: Session) -> dict[str, Any]:
    ensure_guides(db)
    source, parsed, synced_at, note = load_parsed_guides(db)
    stations = parsed.get("stations") or []
    needed: set[str] = set()
    for station in stations:
        for level in station.get("levels") or []:
            needed |= _collect_ids(level.get("item_requirements") or [])
    items = _lookup_items(db, needed)
    public = []
    for station in stations:
        levels = []
        for level in station.get("levels") or []:
            levels.append(
                {
                    **level,
                    "item_requirements": [
                        _enrich_item(req, items)
                        for req in (level.get("item_requirements") or [])
                    ],
                }
            )
        public.append({**station, "levels": levels})
    return {
        "items": public,
        "station_count": len(public),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def get_hideout_station(db: Session, slug: str) -> dict[str, Any]:
    key = (slug or "").strip().lower()
    if not key:
        raise TarkovGuidesError("藏身处 slug 无效")
    catalog = list_hideout(db)
    for row in catalog.get("items") or []:
        if str(row.get("slug") or "").lower() == key or str(row.get("id") or "").lower() == key:
            return {
                **row,
                "source": catalog.get("source"),
                "synced_at": catalog.get("synced_at"),
                "note": catalog.get("note"),
            }
    raise TarkovGuidesError(f"未找到藏身处模块: {slug}")


def _paginate(rows: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    size = min(max(page_size, 1), PAGE_SIZE_MAX)
    total = len(rows)
    pages = max((total + size - 1) // size, 1)
    current = min(max(page, 1), pages)
    start = (current - 1) * size
    return {
        "items": rows[start : start + size],
        "page": current,
        "page_size": size,
        "total": total,
    }


def list_barters(
    db: Session,
    *,
    trader: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    ensure_guides(db)
    source, parsed, synced_at, note = load_parsed_guides(db)
    rows = list(parsed.get("barters") or [])
    trader_key = (trader or "").strip().lower()
    if trader_key:
        rows = [
            r
            for r in rows
            if trader_key in {
                str(r.get("trader_slug") or "").lower(),
                str(r.get("trader_id") or "").lower(),
            }
        ]
    needed: set[str] = set()
    for row in rows:
        needed |= _collect_ids(row.get("required_items") or [])
        offered = row.get("offered_item") or {}
        if offered.get("id"):
            needed.add(str(offered["id"]))
    items = _lookup_items(db, needed)
    needle = (q or "").strip().lower()
    public: list[dict[str, Any]] = []
    for row in rows:
        required = [_enrich_item(req, items) for req in (row.get("required_items") or [])]
        offered = _enrich_item(row.get("offered_item") or {}, items)
        packed = {**row, "required_items": required, "offered_item": offered}
        if needle:
            blob = " ".join(
                [
                    str(packed.get("trader_name") or ""),
                    str(offered.get("name") or ""),
                    *(str(x.get("name") or "") for x in required),
                ]
            ).lower()
            if needle not in blob:
                continue
        public.append(packed)
    paged = _paginate(public, page, page_size)
    traders = sorted(
        {
            (str(r.get("trader_slug") or ""), str(r.get("trader_name") or ""))
            for r in (parsed.get("barters") or [])
            if r.get("trader_slug")
        }
    )
    return {
        **paged,
        "barter_count": paged["total"],
        "traders": [{"slug": slug, "name": name} for slug, name in traders if slug],
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def list_crafts(
    db: Session,
    *,
    station: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    ensure_guides(db)
    source, parsed, synced_at, note = load_parsed_guides(db)
    rows = list(parsed.get("crafts") or [])
    station_key = (station or "").strip().lower()
    if station_key:
        rows = [
            r
            for r in rows
            if station_key in {
                str(r.get("station_slug") or "").lower(),
                str(r.get("station_id") or "").lower(),
            }
        ]
    needed: set[str] = set()
    for row in rows:
        needed |= _collect_ids(row.get("required_items") or [])
        product = row.get("product_item") or {}
        if product.get("id"):
            needed.add(str(product["id"]))
    items = _lookup_items(db, needed)
    needle = (q or "").strip().lower()
    public: list[dict[str, Any]] = []
    for row in rows:
        required = [_enrich_item(req, items) for req in (row.get("required_items") or [])]
        product = _enrich_item(row.get("product_item") or {}, items)
        packed = {**row, "required_items": required, "product_item": product}
        if needle:
            blob = " ".join(
                [
                    str(packed.get("station_name") or ""),
                    str(product.get("name") or ""),
                    *(str(x.get("name") or "") for x in required),
                ]
            ).lower()
            if needle not in blob:
                continue
        public.append(packed)
    paged = _paginate(public, page, page_size)
    stations = sorted(
        {
            (str(r.get("station_slug") or ""), str(r.get("station_name") or ""))
            for r in (parsed.get("crafts") or [])
            if r.get("station_slug")
        }
    )
    return {
        **paged,
        "craft_count": paged["total"],
        "stations": [{"slug": slug, "name": name} for slug, name in stations if slug],
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def guides_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=GUIDES_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "station_count": result.get("station_count"),
                "barter_count": result.get("barter_count"),
                "craft_count": result.get("craft_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov guides sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
