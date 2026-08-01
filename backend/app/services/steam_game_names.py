"""按 AppID 解析游戏显示名与商店卡片（头图 / 价格）。"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timeutil import now_naive, to_naive
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.models.steam_app import SteamApp

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_RETRY_AFTER = timedelta(days=7)
_DETAILS_TTL = timedelta(hours=6)
_UA = "zhange-stats/1.0"
_DESC_MAX = 280


@dataclass
class StoreDetails:
    success: bool
    name: str | None = None
    header_image: str | None = None
    capsule_image: str | None = None
    icon_url: str | None = None
    short_description: str | None = None
    is_free: bool = False
    currency: str | None = None
    initial_price: int | None = None
    final_price: int | None = None
    discount_percent: int | None = None
    initial_formatted: str | None = None
    final_formatted: str | None = None


def _utcnow() -> datetime:
    return now_naive()


def _aware(dt: datetime) -> datetime:
    """库内时间规范为北京墙钟 naive，便于与 _utcnow() 比较。"""
    return to_naive(dt)


def has_cjk(text: str | None) -> bool:
    return bool(text and _CJK_RE.search(text))


def prefer_display_name(
    preferred: str | None, fallback: str | None, app_id: str | None = None
) -> str | None:
    """尽量选中文名；都没有中文时用商店名，再退回 Steam 实时名 / App id。"""
    if has_cjk(preferred):
        return preferred
    if has_cjk(fallback):
        return fallback
    if preferred:
        return preferred
    if fallback:
        return fallback
    if app_id:
        return f"App {app_id}"
    return None


_MIN_ICON_BYTES = 4096


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _http_image_usable(url: str, *, timeout: float = 8) -> bool:
    """GET 校验图片是否真实可用（Steam 对缺失库封面常返回 200 + 极小占位图）。"""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if not (200 <= int(resp.status) < 300):
                return False
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if ctype and "image" not in ctype and "octet-stream" not in ctype:
                return False
            data = resp.read()
            return len(data) >= _MIN_ICON_BYTES
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        ValueError,
    ):
        return False


def _pick_icon_url(
    app_id: str, *, capsule: str | None, header: str | None
) -> str | None:
    """缩略图优先库封面 library_600x900，其次商店 capsule，最后 header。"""
    library = (
        f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/library_600x900.jpg"
    )
    if _http_image_usable(library):
        return library
    if capsule and _http_image_usable(capsule):
        return capsule
    if capsule:
        return capsule
    if header:
        return header
    return None


def _cached_icon_looks_placeholder(url: str | None) -> bool:
    return bool(url and "library_600x900.jpg" in url)


def fetch_store_details(
    app_id: str, *, lang: str = "schinese", cc: str = "cn"
) -> StoreDetails:
    """拉取 Steam 商店详情（简体 + 国区价格）。"""
    app_id = str(app_id).strip()
    if not app_id.isdigit():
        return StoreDetails(success=False)

    params = urllib.parse.urlencode({"appids": app_id, "l": lang, "cc": cc})
    url = f"https://store.steampowered.com/api/appdetails?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        logger.warning("Steam Store appdetails failed for %s: %s", app_id, exc)
        return StoreDetails(success=False)

    entry = (payload or {}).get(app_id) or {}
    if not entry.get("success"):
        return StoreDetails(success=False)

    data: dict[str, Any] = entry.get("data") or {}
    name = str(data.get("name") or "").strip()[:256] or None
    header = str(data.get("header_image") or "").strip()[:512] or None
    capsule = (
        str(data.get("capsule_image") or data.get("capsule_imagev5") or "").strip()[
            :512
        ]
        or None
    )
    raw_desc = str(data.get("short_description") or "").strip()
    desc = _strip_html(raw_desc)[:_DESC_MAX] or None
    is_free = bool(data.get("is_free"))
    price = data.get("price_overview") or {}
    icon_url = _pick_icon_url(app_id, capsule=capsule, header=header)

    return StoreDetails(
        success=True,
        name=name,
        header_image=header,
        capsule_image=capsule,
        icon_url=icon_url,
        short_description=desc,
        is_free=is_free,
        currency=str(price.get("currency") or "").strip()[:8] or None,
        initial_price=int(price["initial"]) if price.get("initial") is not None else None,
        final_price=int(price["final"]) if price.get("final") is not None else None,
        discount_percent=int(price["discount_percent"])
        if price.get("discount_percent") is not None
        else None,
        initial_formatted=str(price.get("initial_formatted") or "").strip()[:32] or None,
        final_formatted=str(price.get("final_formatted") or "").strip()[:32] or None,
    )


def fetch_store_name(app_id: str, lang: str = "schinese") -> str | None:
    details = fetch_store_details(app_id, lang=lang)
    return details.name if details.success else None


def _name_cache_fresh(row: SteamApp, now: datetime) -> bool:
    if row.name:
        return True
    return _aware(row.fetched_at) + _RETRY_AFTER > now


def _details_fresh(row: SteamApp, now: datetime) -> bool:
    if row.details_fetched_at is None:
        return False
    return _aware(row.details_fetched_at) + _DETAILS_TTL > now


def _apply_details(row: SteamApp, details: StoreDetails, now: datetime) -> None:
    if details.name:
        row.name = details.name
    row.header_image = details.header_image
    row.capsule_image = details.capsule_image
    row.icon_url = details.icon_url
    row.short_description = details.short_description
    row.is_free = details.is_free
    row.currency = details.currency
    row.initial_price = details.initial_price
    row.final_price = details.final_price
    row.discount_percent = details.discount_percent
    row.initial_formatted = details.initial_formatted
    row.final_formatted = details.final_formatted
    row.fetched_at = now
    row.details_fetched_at = now if details.success else row.details_fetched_at


def _persist_store_row(
    app_id: str,
    *,
    name: str | None = None,
    details: StoreDetails | None = None,
    fetched_at: datetime | None = None,
) -> None:
    """独立会话写入缓存并回写历史会话名。"""
    now = fetched_at or _utcnow()
    db = SessionLocal()
    try:
        row = db.get(SteamApp, app_id)
        if row is None:
            row = SteamApp(app_id=app_id, fetched_at=now)
            db.add(row)
        if details is not None:
            _apply_details(row, details, now)
            if not details.success and name is not None:
                row.name = name
                row.fetched_at = now
        elif name is not None:
            row.name = name
            row.fetched_at = now

        display = row.name
        if display and has_cjk(display):
            db.query(PlaySession).filter(
                PlaySession.steam_app_id == app_id,
                PlaySession.game_name != display,
            ).update({PlaySession.game_name: display}, synchronize_session=False)
            db.query(PresenceSegment).filter(
                PresenceSegment.steam_app_id == app_id,
                PresenceSegment.game_name != display,
            ).update({PresenceSegment.game_name: display}, synchronize_session=False)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("persist steam app cache failed for %s", app_id)
    finally:
        db.close()


def resolve_app_names(
    db: Session,
    app_ids: Iterable[str | None],
    *,
    fetch_missing: bool = True,
) -> dict[str, str]:
    """批量解析 AppID → 显示名（优先已缓存的商店简体名）。"""
    ids = sorted({str(a).strip() for a in app_ids if a and str(a).strip()})
    if not ids:
        return {}

    rows = db.query(SteamApp).filter(SteamApp.app_id.in_(ids)).all()
    by_id = {r.app_id: r for r in rows}
    now = _utcnow()
    result: dict[str, str] = {}

    for app_id in ids:
        row = by_id.get(app_id)
        if row and row.name and _name_cache_fresh(row, now):
            result[app_id] = row.name
            continue
        if row and not row.name and _name_cache_fresh(row, now):
            continue
        if not fetch_missing:
            if row and row.name:
                result[app_id] = row.name
            continue

        details = fetch_store_details(app_id)
        _persist_store_row(app_id, details=details, fetched_at=now)
        by_id[app_id] = SteamApp(
            app_id=app_id,
            name=details.name,
            fetched_at=now,
        )
        if details.name:
            result[app_id] = details.name

    return result


def display_name_for(
    db: Session,
    app_id: str | None,
    fallback: str | None = None,
    *,
    fetch_missing: bool = True,
) -> str | None:
    if not app_id:
        return prefer_display_name(None, fallback, None)
    names = resolve_app_names(db, [app_id], fetch_missing=fetch_missing)
    return prefer_display_name(names.get(app_id), fallback, app_id)


def resolve_app_icons(
    db: Session,
    app_ids: Iterable[str | None],
    *,
    fetch_missing: bool = True,
) -> dict[str, str]:
    """批量解析 AppID → 缩略图 URL（库封面 / capsule）。"""
    ids = sorted({str(a).strip() for a in app_ids if a and str(a).strip()})
    if not ids:
        return {}

    rows = db.query(SteamApp).filter(SteamApp.app_id.in_(ids)).all()
    by_id = {r.app_id: r for r in rows}
    now = _utcnow()
    result: dict[str, str] = {}

    for app_id in ids:
        row = by_id.get(app_id)
        if (
            row
            and row.icon_url
            and _details_fresh(row, now)
            and not _cached_icon_looks_placeholder(row.icon_url)
        ):
            result[app_id] = row.icon_url
            continue
        if (
            row
            and row.icon_url
            and _details_fresh(row, now)
            and _cached_icon_looks_placeholder(row.icon_url)
            and _http_image_usable(row.icon_url)
        ):
            result[app_id] = row.icon_url
            continue
        if not fetch_missing:
            if row and row.icon_url:
                result[app_id] = row.icon_url
            continue
        details = fetch_store_details(app_id)
        if details.success:
            _persist_store_row(app_id, details=details, fetched_at=now)
            if details.icon_url:
                result[app_id] = details.icon_url
        elif row and row.icon_url:
            result[app_id] = row.icon_url

    return result


def _serialize_store_card(row: SteamApp) -> dict[str, Any]:
    return {
        "steam_app_id": row.app_id,
        "name": row.name,
        "header_image": row.header_image,
        "capsule_image": row.capsule_image,
        "icon_url": row.icon_url,
        "short_description": row.short_description,
        "is_free": bool(row.is_free),
        "currency": row.currency,
        "initial_price": row.initial_price,
        "final_price": row.final_price,
        "discount_percent": row.discount_percent or 0,
        "initial_formatted": row.initial_formatted,
        "final_formatted": row.final_formatted,
        "store_url": f"https://store.steampowered.com/app/{row.app_id}",
    }


def get_store_card(db: Session, app_id: str) -> dict[str, Any] | None:
    """返回商店悬停卡片数据；按 TTL 刷新价格与头图。"""
    app_id = str(app_id).strip()
    if not app_id.isdigit():
        return None

    now = _utcnow()
    row = db.get(SteamApp, app_id)
    needs_refresh = (
        row is None
        or not _details_fresh(row, now)
        or not row.header_image
        or not row.icon_url
    )
    if needs_refresh:
        details = fetch_store_details(app_id)
        if details.success:
            _persist_store_row(app_id, details=details, fetched_at=now)
            return {
                "steam_app_id": app_id,
                "name": details.name or (row.name if row else None),
                "header_image": details.header_image,
                "capsule_image": details.capsule_image,
                "icon_url": details.icon_url,
                "short_description": details.short_description,
                "is_free": bool(details.is_free),
                "currency": details.currency,
                "initial_price": details.initial_price,
                "final_price": details.final_price,
                "discount_percent": details.discount_percent or 0,
                "initial_formatted": details.initial_formatted,
                "final_formatted": details.final_formatted,
                "store_url": f"https://store.steampowered.com/app/{app_id}",
            }
        if row is None:
            return None

    return _serialize_store_card(row)
