"""逃离塔科夫藏身处 / 以物易物 / 制作：json.tarkov.dev raw → 列表投影。"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovGuidesMeta, TarkovGuidesRaw
from app.services.tarkov_ammo import SOURCE_JSON_API
from app.services.tarkov_tasks import TRADER_BY_ID

logger = logging.getLogger(__name__)

META_ROW_ID = 1
RAW_ROW_ID = 1
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
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "zhange-stats/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise TarkovGuidesError(f"下载失败 HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise TarkovGuidesError(f"无法连接资源站: {exc}") from exc


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
    hideout_payload = _download_json(TARKOV_JSON_HIDEOUT_URL)
    hideout = hideout_payload.get("data")
    if not isinstance(hideout, dict) or not hideout:
        raise TarkovGuidesError("json.tarkov.dev hideout 为空")

    locale: dict[str, Any] = {}
    try:
        loc_payload = _download_json(TARKOV_JSON_HIDEOUT_LOCALE_URL.format(lang=lang))
        loc_data = loc_payload.get("data")
        if isinstance(loc_data, dict):
            locale = loc_data
    except TarkovGuidesError:
        logger.warning("json.tarkov.dev hideout_%s locale unavailable", lang)

    barters_payload = _download_json(TARKOV_JSON_BARTERS_URL)
    barters = barters_payload.get("data")
    if not isinstance(barters, list):
        raise TarkovGuidesError("json.tarkov.dev barters 格式无效")

    crafts_payload = _download_json(TARKOV_JSON_CRAFTS_URL)
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
        note="json.tarkov.dev/regular/hideout+barters+crafts",
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


def get_guides_raw(db: Session) -> TarkovGuidesRaw | None:
    return db.get(TarkovGuidesRaw, RAW_ROW_ID)


def get_guides_meta(db: Session) -> TarkovGuidesMeta | None:
    return db.get(TarkovGuidesMeta, META_ROW_ID)


def persist_guides_bundle(db: Session, bundle: GuidesUpstreamBundle) -> dict[str, Any]:
    global _parsed_cache
    stations = parse_hideout_stations(bundle.payload)
    barters = parse_barters(bundle.payload)
    crafts = parse_crafts(bundle.payload)
    if not stations:
        raise TarkovGuidesError("未解析到藏身处数据")
    now = now_naive()
    raw_json = json.dumps(bundle.payload, ensure_ascii=False)
    row = get_guides_raw(db)
    if row is None:
        db.add(
            TarkovGuidesRaw(
                id=RAW_ROW_ID,
                source=bundle.source,
                raw_json=raw_json,
                synced_at=now,
                note=bundle.note,
            )
        )
    else:
        row.source = bundle.source
        row.raw_json = raw_json
        row.synced_at = now
        row.note = bundle.note
    meta = get_guides_meta(db)
    if meta is None:
        meta = TarkovGuidesMeta(id=META_ROW_ID)
        db.add(meta)
    meta.source = bundle.source
    meta.station_count = len(stations)
    meta.barter_count = len(barters)
    meta.craft_count = len(crafts)
    meta.synced_at = now
    meta.note = bundle.note
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


def sync_from_upstream(db: Session) -> dict[str, Any]:
    logger.info("syncing tarkov hideout/barters/crafts from upstream")
    return persist_guides_bundle(db, download_json_guides(lang="zh"))


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    row = get_guides_raw(db)
    if row is None:
        raise TarkovGuidesError("无藏身处 / 交换 raw")
    try:
        payload = json.loads(row.raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TarkovGuidesError("guides raw_json 无效") from exc
    if not isinstance(payload, dict):
        raise TarkovGuidesError("guides raw_json 格式无效")
    meta = get_guides_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    note = (meta.note if meta else None) or row.note
    return row.source, payload, synced, note


def load_parsed_guides(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    global _parsed_cache
    meta = get_guides_meta(db)
    synced = meta.synced_at.isoformat() if meta and meta.synced_at else None
    key = synced or ""
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
    if get_guides_raw(db) is None:
        sync_from_upstream(db)


def _lookup_items(db: Session, item_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not item_ids:
        return {}
    try:
        from app.services import tarkov_catalog as catalog_svc
        from app.services import tarkov_items as items_svc

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
