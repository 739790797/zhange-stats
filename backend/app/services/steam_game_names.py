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


_CLIENT_ICON_MARKER = "steamcommunity/public/images/apps/"
# app_id → 上次尝试补全 client icon 的时间戳（进程内，避免每次请求都打 GetOwnedGames）
_client_icon_fetch_at: dict[str, float] = {}
_CLIENT_ICON_FETCH_TTL_SEC = 6 * 3600


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _is_client_icon_url(url: str | None) -> bool:
    """是否为 Steam 库列表左侧小图标（非商店 capsule/header）。"""
    return bool(url and _CLIENT_ICON_MARKER in url)


def _should_fetch_client_icon(app_id: str) -> bool:
    import time

    ts = _client_icon_fetch_at.get(app_id)
    return ts is None or (time.time() - ts) >= _CLIENT_ICON_FETCH_TTL_SEC


def _mark_client_icon_fetched(app_ids: Iterable[str]) -> None:
    import time

    now = time.time()
    for app_id in app_ids:
        _client_icon_fetch_at[app_id] = now


def _http_url_ok(url: str, *, min_bytes: int = 200, timeout: float = 8) -> bool:
    """校验图片 URL 可下载（部分新游戏的 client icon hash 会 404）。"""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if not (200 <= int(resp.status) < 300):
                return False
            data = resp.read(min_bytes + 1)
            return len(data) >= min_bytes
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        ValueError,
    ):
        return False


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

    return StoreDetails(
        success=True,
        name=name,
        header_image=header,
        capsule_image=capsule,
        icon_url=None,
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
    # 不覆盖已缓存的库列表 client icon
    if details.icon_url and _is_client_icon_url(details.icon_url):
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
    """批量解析 AppID → 库列表小图标 URL（不含商店 capsule/header）。

    仅返回真正的 client icon；缺失时可选经 GetOwnedGames 补全。
    """
    ids = sorted({str(a).strip() for a in app_ids if a and str(a).strip()})
    if not ids:
        return {}

    rows = db.query(SteamApp).filter(SteamApp.app_id.in_(ids)).all()
    by_id = {r.app_id: r for r in rows}
    result: dict[str, str] = {}
    need_fetch: list[str] = []

    for app_id in ids:
        row = by_id.get(app_id)
        icon = (row.icon_url or "").strip() if row else ""
        if _is_client_icon_url(icon):
            result[app_id] = icon
            continue
        if fetch_missing and _should_fetch_client_icon(app_id):
            need_fetch.append(app_id)

    if need_fetch:
        _fill_client_icons_from_owned_games(db, need_fetch, result)
        _mark_client_icon_fetched(need_fetch)
        for app_id in need_fetch:
            if app_id in result and _is_client_icon_url(result[app_id]):
                continue
            row = by_id.get(app_id) or db.get(SteamApp, app_id)
            if row and _is_client_icon_url(row.icon_url):
                result[app_id] = row.icon_url  # type: ignore[assignment]

    # 丢掉误写入的非 client icon
    return {k: v for k, v in result.items() if _is_client_icon_url(v)}


def _candidate_steam_ids_for_icons(db: Session, app_ids: list[str]) -> list[str]:
    """优先用玩过这些游戏的成员库，再退回任意已绑定 Steam 的成员。"""
    from app.models.member import Member

    ordered: list[str] = []
    seen: set[str] = set()

    def _push(sid: str | None) -> None:
        s = (sid or "").strip()
        if s and s not in seen:
            seen.add(s)
            ordered.append(s)

    if app_ids:
        players = (
            db.query(Member.steam_id)
            .join(PlaySession, PlaySession.member_id == Member.id)
            .filter(
                Member.steam_id.isnot(None),
                PlaySession.steam_app_id.in_(app_ids),
            )
            .distinct()
            .limit(8)
            .all()
        )
        for (sid,) in players:
            _push(sid)

    others = (
        db.query(Member.steam_id)
        .filter(Member.steam_id.isnot(None))
        .limit(12)
        .all()
    )
    for (sid,) in others:
        _push(sid)
    return ordered


def _client_icon_cdn_url(app_id: str, icon_hash: str) -> str:
    return (
        "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/"
        f"apps/{app_id}/{icon_hash}.jpg"
    )


def _fetch_icon_hash_from_steamcmd(app_id: str) -> str | None:
    """从 steamcmd 公开 appinfo 取库列表 icon hash（无需 Steam API Key / 游戏库）。"""
    app_id = str(app_id).strip()
    if not app_id.isdigit():
        return None
    url = f"https://api.steamcmd.net/v1/info/{app_id}"
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
        logger.warning("steamcmd appinfo failed for %s: %s", app_id, exc)
        return None

    data = (payload or {}).get("data") or {}
    entry = data.get(app_id) or data.get(str(app_id)) or {}
    common = entry.get("common") if isinstance(entry, dict) else None
    if not isinstance(common, dict):
        return None
    icon_hash = str(common.get("icon") or "").strip().lower()
    if re.fullmatch(r"[a-f0-9]{40}", icon_hash):
        return icon_hash
    return None


def _persist_client_icon(
    db: Session, app_id: str, url: str, *, now: datetime
) -> None:
    row = db.get(SteamApp, app_id)
    if row is None:
        row = SteamApp(app_id=app_id, fetched_at=now, icon_url=url)
        db.add(row)
    else:
        row.icon_url = url


def _fill_client_icons_from_steamcmd(
    db: Session, missing: list[str], result: dict[str, str]
) -> None:
    """无游戏库可查时：用 steamcmd 公开 appinfo 补 client icon hash。"""
    now = _utcnow()
    for app_id in missing:
        if app_id in result and _is_client_icon_url(result.get(app_id)):
            continue
        icon_hash = _fetch_icon_hash_from_steamcmd(app_id)
        if not icon_hash:
            continue
        url = _client_icon_cdn_url(app_id, icon_hash)
        if not _http_url_ok(url):
            continue
        try:
            _persist_client_icon(db, app_id, url, now=now)
            db.commit()
            result[app_id] = url
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("persist steamcmd client icon failed for %s", app_id)


def _fill_client_icons_from_owned_games(
    db: Session, missing: list[str], result: dict[str, str]
) -> None:
    """统一走真实补全：优先 GetOwnedGames，仍缺则 steamcmd appinfo。

    与是否开启假监控无关——假监控只伪造用户在线/游玩状态。
    """
    from app.services.adapters.steam import SteamAdapter
    from app.services.integrations_config import get_steam_api_key

    steam_key = get_steam_api_key(db)
    still = set(missing)

    if steam_key:
        adapter = SteamAdapter(steam_key)
        now = _utcnow()

        for steam_id in _candidate_steam_ids_for_icons(db, missing):
            if not still:
                break
            try:
                icons = adapter.fetch_owned_game_icons(steam_id)
            except Exception:  # noqa: BLE001
                logger.exception("GetOwnedGames icons failed for %s", steam_id)
                continue
            if not icons:
                continue

            # 只写入当前缺图标的 app，避免一次扫整库写几百行
            for app_id in list(still):
                url = icons.get(app_id)
                if not url or not _http_url_ok(url):
                    continue
                try:
                    _persist_client_icon(db, app_id, url, now=now)
                    result[app_id] = url
                    still.discard(app_id)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "prepare client icon row failed for %s", app_id
                    )
            try:
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("persist client icons failed")

    if still:
        _fill_client_icons_from_steamcmd(db, sorted(still), result)

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
    )
    if needs_refresh:
        details = fetch_store_details(app_id)
        if details.success:
            _persist_store_row(app_id, details=details, fetched_at=now)
            row = db.get(SteamApp, app_id)
            card = {
                "steam_app_id": app_id,
                "name": details.name or (row.name if row else None),
                "header_image": details.header_image,
                "capsule_image": details.capsule_image,
                "icon_url": None,
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
            if row and _is_client_icon_url(row.icon_url):
                card["icon_url"] = row.icon_url
            return card
        if row is None:
            return None

    card = _serialize_store_card(row)
    if not _is_client_icon_url(card.get("icon_url")):
        card["icon_url"] = None
    return card
