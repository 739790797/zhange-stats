"""逃离塔科夫商人：json traders 元数据 + 物品 buyFromTrader 报价。"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.tarkov import TarkovTradersRaw
from app.services.tarkov.ammo import SOURCE_JSON_API
from app.services.tarkov.game_mode import (
    cache_key,
    json_api_prefix,
    json_resource_url,
    parse_game_mode,
    run_for_modes,
)
from app.services.tarkov.http import download_bytes

logger = logging.getLogger(__name__)

TRADERS_JOB_KEY = "tarkov_traders_sync"
TRADERS_PAGE_SIZE_DEFAULT = 50
TRADERS_PAGE_SIZE_MAX = 100
DOWNLOAD_TIMEOUT = 180

TARKOV_JSON_TRADERS_URL = "https://json.tarkov.dev/regular/traders"
TARKOV_JSON_TRADERS_LOCALE_URL = "https://json.tarkov.dev/regular/traders_{lang}"

# slug → (英文, 社区简称)
TRADER_LABELS: dict[str, tuple[str, str]] = {
    "prapor": ("Prapor", "俄商"),
    "therapist": ("Therapist", "大妈"),
    "fence": ("Fence", "黑商"),
    "skier": ("Skier", "走私客"),
    "peacekeeper": ("Peacekeeper", "美商"),
    "mechanic": ("Mechanic", "机械师"),
    "ragman": ("Ragman", "服装商"),
    "jaeger": ("Jaeger", "耶格"),
    "lightkeeper": ("Lightkeeper", "灯塔商人"),
    "ref": ("Ref", "竞技场裁判"),
    "btr-driver": ("BTR Driver", "BTR"),
}

TRADER_WIKI: dict[str, str] = {
    "prapor": "https://escapefromtarkov.fandom.com/wiki/Prapor",
    "therapist": "https://escapefromtarkov.fandom.com/wiki/Therapist",
    "fence": "https://escapefromtarkov.fandom.com/wiki/Fence",
    "skier": "https://escapefromtarkov.fandom.com/wiki/Skier",
    "peacekeeper": "https://escapefromtarkov.fandom.com/wiki/Peacekeeper",
    "mechanic": "https://escapefromtarkov.fandom.com/wiki/Mechanic",
    "ragman": "https://escapefromtarkov.fandom.com/wiki/Ragman",
    "jaeger": "https://escapefromtarkov.fandom.com/wiki/Jaeger",
    "lightkeeper": "https://escapefromtarkov.fandom.com/wiki/Lightkeeper",
    "ref": "https://escapefromtarkov.fandom.com/wiki/Ref",
    "btr-driver": "https://escapefromtarkov.fandom.com/wiki/BTR_Driver",
}

TRADER_SLUG_ORDER = list(TRADER_LABELS.keys())

_parsed_lock = threading.Lock()
_parsed_cache: tuple[str, list[dict[str, Any]], list[dict[str, Any]]] | None = None


class TarkovTradersError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class TradersUpstreamBundle:
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
        error_cls=TarkovTradersError,
    )


def _as_int(value: Any, default: int | None = 0) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _id_of(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("_id") or "").strip()
    if value is None:
        return ""
    return str(value).strip()


def _english_name(slug: str, raw_name: str = "") -> str:
    if slug in TRADER_LABELS:
        return TRADER_LABELS[slug][0]
    name = (raw_name or "").strip()
    if name and slug not in name.lower() and "nickname" not in name.lower():
        return name
    return slug.replace("-", " ").title()


def _chinese_name(slug: str) -> str:
    if slug in TRADER_LABELS:
        return TRADER_LABELS[slug][1]
    return ""


def _traders_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    blob = payload.get("traders")
    if not isinstance(blob, dict):
        blob = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if not isinstance(blob, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in blob.items():
        if not isinstance(value, dict):
            continue
        if value.get("normalizedName") or value.get("levels") is not None:
            out[str(key)] = value
    return out


def _locale_map(payload: dict[str, Any]) -> dict[str, Any]:
    locale = payload.get("locale")
    return locale if isinstance(locale, dict) else {}


def _offers_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    offers = payload.get("offers")
    if isinstance(offers, list):
        return [row for row in offers if isinstance(row, dict)]
    return []


def trader_portrait_url(slug: str) -> str:
    slug = (slug or "").strip()
    if not slug:
        return ""
    return f"https://tarkov.dev/images/traders/{slug}-portrait.png"


def download_json_api_traders(*, lang: str = "zh") -> TradersUpstreamBundle:
    raw = _http_request(json_resource_url("traders"), timeout=60)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovTradersError("json.tarkov.dev traders 解析失败") from exc
    if not isinstance(payload, dict) or not _traders_map(payload):
        raise TarkovTradersError("json.tarkov.dev 未解析到商人")
    try:
        loc_raw = _http_request(
            json_resource_url("traders", lang=lang),
            timeout=30,
        )
        loc_payload = json.loads(loc_raw.decode("utf-8"))
        loc_data = loc_payload.get("data") if isinstance(loc_payload, dict) else None
        if isinstance(loc_data, dict) and loc_data:
            payload = dict(payload)
            payload["locale"] = loc_data
    except TarkovTradersError:
        logger.warning("json.tarkov.dev traders_%s locale unavailable", lang)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("json.tarkov.dev traders_%s locale parse failed", lang)
    return TradersUpstreamBundle(
        source=SOURCE_JSON_API,
        payload=payload,
        note=f"json.tarkov.dev/{json_api_prefix()}/traders",
    )


def extract_offers_from_items(items_source: str, items_payload: dict[str, Any]) -> list[dict[str, Any]]:
    from app.services.tarkov import catalog as catalog_svc
    from app.services.tarkov import items as items_svc

    locale = items_svc._locale_map(items_payload)
    offers: list[dict[str, Any]] = []
    for item_id, raw in catalog_svc.iter_raw_items(items_source, items_payload):
        buys = raw.get("buyFromTrader")
        if not isinstance(buys, list) or not buys:
            continue
        name, short_name, _desc = catalog_svc._localized_name(item_id, raw, locale)
        types = raw.get("types") if isinstance(raw.get("types"), list) else []
        icon = str(raw.get("baseImageLink") or raw.get("iconLink") or "")
        avg = _as_int(raw.get("avg24hPrice"), None)
        low = _as_int(raw.get("lastLowPrice"), None)
        for row in buys:
            if not isinstance(row, dict):
                continue
            trader_id = _id_of(row.get("trader"))
            if not trader_id:
                continue
            unlock = row.get("taskUnlock")
            unlock_id = _id_of(unlock)
            unlock_name = ""
            if isinstance(unlock, dict):
                unlock_name = str(unlock.get("name") or "").strip()
            offers.append(
                {
                    "trader_id": trader_id,
                    "item_id": item_id,
                    "name": name,
                    "short_name": short_name,
                    "icon_link": icon,
                    "types": [str(t) for t in types if t is not None and str(t).strip()],
                    "avg24h_price": avg,
                    "last_low_price": low,
                    "price": _as_int(row.get("price"), 0) or 0,
                    "price_rub": _as_int(row.get("priceRUB"), 0) or 0,
                    "currency": str(row.get("currency") or "RUB"),
                    "min_trader_level": _as_int(row.get("minTraderLevel"), 1) or 1,
                    "buy_limit": _as_int(row.get("buyLimit"), None),
                    "task_unlock_id": unlock_id,
                    "task_unlock_name": unlock_name,
                }
            )
    return offers


def project_trader(
    trader_id: str,
    raw: dict[str, Any],
    locale: dict[str, Any],
    *,
    offer_count: int = 0,
) -> dict[str, Any] | None:
    slug = str(raw.get("normalizedName") or "").strip()
    if not slug:
        return None
    english = _english_name(slug, str(raw.get("name") or ""))
    chinese = _chinese_name(slug)
    desc = str(locale.get(f"{trader_id} Description") or "").strip()
    if trader_id and desc.endswith(" Description") and trader_id in desc:
        desc = ""
    if not desc:
        raw_desc = str(raw.get("description") or "").strip()
        if raw_desc and " Description" not in raw_desc:
            desc = raw_desc
    levels = []
    for row in raw.get("levels") or []:
        if not isinstance(row, dict):
            continue
        levels.append(
            {
                "level": _as_int(row.get("level"), 0) or 0,
                "required_player_level": _as_int(row.get("requiredPlayerLevel"), 0) or 0,
                "required_reputation": float(row.get("requiredReputation") or 0),
                "required_commerce": _as_int(row.get("requiredCommerce"), 0) or 0,
            }
        )
    levels.sort(key=lambda r: r["level"])
    currency = raw.get("currency")
    if isinstance(currency, dict):
        currency_name = str(currency.get("name") or currency.get("normalizedName") or "RUB")
    else:
        currency_name = str(currency or "RUB")
    return {
        "id": trader_id,
        "slug": slug,
        "english": english,
        "chinese": chinese,
        "name": f"{english}（{chinese}）" if chinese else english,
        "description": desc,
        "image_link": str(raw.get("imageLink") or ""),
        "portrait_link": trader_portrait_url(slug),
        "wiki_link": TRADER_WIKI.get(slug)
        or (
            f"https://escapefromtarkov.fandom.com/wiki/{english.replace(' ', '_')}"
            if english
            else ""
        ),
        "reset_time": str(raw.get("resetTime") or ""),
        "currency": currency_name,
        "levels": levels,
        "offer_count": offer_count,
    }


def parse_trader_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locale = _locale_map(payload)
    offers = _offers_list(payload)
    counts: dict[str, int] = {}
    for row in offers:
        tid = str(row.get("trader_id") or "")
        if tid:
            counts[tid] = counts.get(tid, 0) + 1
    rows: list[dict[str, Any]] = []
    for trader_id, raw in _traders_map(payload).items():
        row = project_trader(trader_id, raw, locale, offer_count=counts.get(trader_id, 0))
        if row:
            rows.append(row)
    order = {slug: i for i, slug in enumerate(TRADER_SLUG_ORDER)}
    rows.sort(key=lambda r: (order.get(r["slug"], 100), r["english"]))
    return rows


def filter_offers(
    offers: list[dict[str, Any]],
    *,
    trader_id: str,
    level: int | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    out: list[dict[str, Any]] = []
    for row in offers:
        if str(row.get("trader_id") or "") != trader_id:
            continue
        if level is not None and int(row.get("min_trader_level") or 0) != int(level):
            continue
        if needle:
            blob = " ".join(
                [
                    str(row.get("name") or ""),
                    str(row.get("short_name") or ""),
                    str(row.get("item_id") or ""),
                ]
            ).lower()
            if needle not in blob:
                continue
        out.append(row)
    out.sort(
        key=lambda r: (
            int(r.get("min_trader_level") or 0),
            str(r.get("name") or ""),
        )
    )
    return out


def paginate_offers(
    rows: list[dict[str, Any]],
    *,
    page: int = 1,
    page_size: int = TRADERS_PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    try:
        size = int(page_size)
    except (TypeError, ValueError):
        size = TRADERS_PAGE_SIZE_DEFAULT
    size = max(1, min(size, TRADERS_PAGE_SIZE_MAX))
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
        "offer_count": total,
        "page": page_n,
        "page_size": size,
    }


def get_traders_raw(db: Session) -> TarkovTradersRaw | None:
    from app.services.tarkov import upstream as upstream_svc

    return upstream_svc.load_raw_row(db, "traders")


def persist_traders_bundle(db: Session, bundle: TradersUpstreamBundle) -> dict[str, Any]:
    from app.services.tarkov import upstream as upstream_svc

    rows = parse_trader_rows(bundle.payload)
    if not rows:
        raise TarkovTradersError("未解析到商人数据")
    now = now_naive()
    offer_count = len(_offers_list(bundle.payload))
    store = {k: v for k, v in bundle.payload.items() if k != "locale"}
    traders = store.get("traders")
    if isinstance(traders, dict):
        store = {"data": traders}
    upstream_svc.persist_raw(
        db,
        "traders",
        store,
        source=bundle.source,
        note=bundle.note,
        commit=False,
    )
    upstream_svc.persist_locale_if_present(
        db,
        "traders",
        bundle.payload,
        source=bundle.source,
        note=bundle.note,
    )
    db.commit()
    global _parsed_cache
    with _parsed_lock:
        _parsed_cache = None
    return {
        "trader_count": len(rows),
        "offer_count": offer_count,
        "source": bundle.source,
        "synced_at": now.isoformat() if now else None,
        "note": bundle.note,
    }


def _sync_current_mode(db: Session) -> dict[str, Any]:
    mode = parse_game_mode()
    logger.info("syncing tarkov traders from upstream (%s)", mode)
    return persist_traders_bundle(db, download_json_api_traders(lang="zh"))


def sync_from_upstream(db: Session, *, game_mode: str | None = None) -> dict[str, Any]:
    return run_for_modes(
        lambda: _sync_current_mode(db),
        game_mode=game_mode,
        error_cls=TarkovTradersError,
        label="商人",
    )


def _load_payload(db: Session) -> tuple[str, dict[str, Any], str | None, str | None]:
    from app.services.tarkov import upstream as upstream_svc

    source, payload, synced, note = upstream_svc.load_main_payload(
        db,
        "traders",
        error_cls=TarkovTradersError,
        missing="无商人 raw",
        invalid="商人 raw_json 无效",
    )
    if not _offers_list(payload):
        try:
            from app.services.tarkov import catalog as catalog_svc

            items_source, items_payload, _synced, _note = catalog_svc._load_payload(db)
            if catalog_svc.payload_has_full_items(items_source, items_payload):
                payload = dict(payload)
                payload["offers"] = extract_offers_from_items(items_source, items_payload)
        except Exception:  # noqa: BLE001
            logger.warning("traders offers from items unavailable", exc_info=True)
    return source, payload, synced, note


def ensure_traders(db: Session) -> None:
    if get_traders_raw(db) is not None:
        return
    sync_from_upstream(db, game_mode=parse_game_mode())


def load_parsed_traders(
    db: Session,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str | None, str | None]:
    global _parsed_cache
    ensure_traders(db)
    row = get_traders_raw(db)
    synced = row.synced_at.isoformat() if row and row.synced_at else None
    key = cache_key(synced or "")
    with _parsed_lock:
        cached = _parsed_cache
        if cached is not None and cached[0] == key:
            source, _payload, synced_at, note = _load_payload(db)
            return source, cached[1], cached[2], synced_at, note
    source, payload, synced_at, note = _load_payload(db)
    rows = parse_trader_rows(payload)
    offers = _offers_list(payload)
    with _parsed_lock:
        _parsed_cache = (key, rows, offers)
    return source, rows, offers, synced_at, note


def list_traders(db: Session) -> dict[str, Any]:
    source, rows, _offers, synced_at, note = load_parsed_traders(db)
    return {
        "items": rows,
        "trader_count": len(rows),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def get_trader_detail(
    db: Session,
    slug: str,
    *,
    level: int | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = TRADERS_PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    slug = (slug or "").strip().lower()
    if not slug:
        raise TarkovTradersError("商人 slug 无效")
    source, rows, offers, synced_at, note = load_parsed_traders(db)
    trader = next((r for r in rows if r.get("slug") == slug), None)
    if trader is None:
        raise TarkovTradersError(f"未找到商人: {slug}")
    filtered = filter_offers(
        offers,
        trader_id=str(trader.get("id") or ""),
        level=level,
        q=q,
    )
    paged = paginate_offers(filtered, page=page, page_size=page_size)
    return {
        **trader,
        "items": paged["items"],
        "offer_count": paged["offer_count"],
        "page": paged["page"],
        "page_size": paged["page_size"],
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def traders_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=TRADERS_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_from_upstream(db)
        job.status = "ok"
        job.message = json.dumps(
            {
                "trader_count": result.get("trader_count"),
                "offer_count": result.get("offer_count"),
                "source": result.get("source"),
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov traders sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
