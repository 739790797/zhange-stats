"""按 AppID 解析游戏显示名与商店卡片（头图 / 价格）。"""

from __future__ import annotations

import logging
import re
import threading
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.database import SessionLocal
from app.core.http_client import HttpRequestError, http_request
from app.core.timeutil import now_naive, to_naive
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.models.steam_app import SteamApp

logger = logging.getLogger(__name__)

APP_ID_PATTERN = r"^\d{1,10}$"
_APP_ID_RE = re.compile(APP_ID_PATTERN)
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_RETRY_AFTER = timedelta(days=7)
_DETAILS_TTL = timedelta(hours=6)
_DETAILS_MISS_RETRY = timedelta(hours=6)
_ICON_MISS_RETRY = timedelta(days=1)
# 补一枚图标最多查几位玩过该游戏的成员库：GetOwnedGames 吃站点 Steam key 的每日配额
_OWNED_GAMES_CALLS_MAX = 2
_FLIGHT_WAIT_SEC = 30.0
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


def _aware(dt: datetime) -> datetime:
    """库内时间规范为北京墙钟 naive，便于与 now_naive() 比较。"""
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

_flight_guard = threading.Lock()
_flights: dict[str, threading.Lock] = {}


def is_valid_app_id(app_id: str | None) -> bool:
    return bool(app_id) and _APP_ID_RE.fullmatch(str(app_id)) is not None


def is_known_app(db: Session, app_id: str) -> bool:
    """只回源站内出现过的 AppID（游玩记录 / 在线片段 / 商店缓存），任意 id 不消耗站点 Steam 配额。"""
    if db.get(SteamApp, app_id) is not None:
        return True
    for column in (PlaySession.steam_app_id, PresenceSegment.steam_app_id):
        if db.query(column).filter(column == app_id).limit(1).first() is not None:
            return True
    return False


def _missed_recently(
    missed_at: datetime | None, retry_after: timedelta, now: datetime
) -> bool:
    return missed_at is not None and _aware(missed_at) + retry_after > now


@contextmanager
def _single_flight(key: str) -> Iterator[bool]:
    """同一 key 同时只放一个请求回源；其余等它结束（最多 _FLIGHT_WAIT_SEC）后读库，不再回源。

    yield True：本请求负责回源；False：别人刚回源完（或等超时），只读库里的结果。
    """
    with _flight_guard:
        lock = _flights.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        if lock.acquire(timeout=_FLIGHT_WAIT_SEC):
            lock.release()
        yield False
        return
    try:
        yield True
    finally:
        with _flight_guard:
            if _flights.get(key) is lock:
                del _flights[key]
        lock.release()


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _is_client_icon_url(url: str | None) -> bool:
    """是否为 Steam 库列表左侧小图标（非商店 capsule/header）。"""
    return bool(url and _CLIENT_ICON_MARKER in url)


def _http_url_ok(url: str, *, min_bytes: int = 200, timeout: float = 8) -> bool:
    """校验图片 URL 可下载（部分新游戏的 client icon hash 会 404）。"""
    try:
        resp = http_request(
            "GET", url, headers={"User-Agent": _UA}, timeout=timeout
        )
    except HttpRequestError:
        return False
    return 200 <= resp.status_code < 300 and len(resp.content) >= min_bytes


def fetch_store_details(
    app_id: str, *, lang: str = "schinese", cc: str = "cn"
) -> StoreDetails:
    """拉取 Steam 商店详情（简体 + 国区价格）。"""
    app_id = str(app_id).strip()
    if not is_valid_app_id(app_id):
        return StoreDetails(success=False)

    params = urllib.parse.urlencode({"appids": app_id, "l": lang, "cc": cc})
    url = f"https://store.steampowered.com/api/appdetails?{params}"
    try:
        resp = http_request(
            "GET", url, headers={"User-Agent": _UA}, timeout=15
        )
        payload = resp.json()
    except (HttpRequestError, ValueError, OSError) as exc:
        logger.debug("Steam Store appdetails failed for %s: %s", app_id, exc)
        return StoreDetails(success=False)
    if resp.status_code >= 400 or not isinstance(payload, dict):
        logger.debug("Steam Store appdetails failed for %s: HTTP %s", app_id, resp.status_code)
        return StoreDetails(success=False)

    entry = payload.get(app_id)
    if not isinstance(entry, dict) or not entry.get("success"):
        return StoreDetails(success=False)

    data = entry.get("data")
    if not isinstance(data, dict):
        data = {}
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
    price = data.get("price_overview")
    if not isinstance(price, dict):
        price = {}

    return StoreDetails(
        success=True,
        name=name,
        header_image=header,
        capsule_image=capsule,
        icon_url=None,
        short_description=desc,
        is_free=is_free,
        currency=str(price.get("currency") or "").strip()[:8] or None,
        initial_price=_int_or_none(price.get("initial")),
        final_price=_int_or_none(price.get("final")),
        discount_percent=_int_or_none(price.get("discount_percent")),
        initial_formatted=str(price.get("initial_formatted") or "").strip()[:32] or None,
        final_formatted=str(price.get("final_formatted") or "").strip()[:32] or None,
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _name_cache_fresh(row: SteamApp, now: datetime) -> bool:
    if row.name:
        return True
    return _missed_recently(row.details_missed_at, _RETRY_AFTER, now)


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
    details: StoreDetails,
    *,
    fetched_at: datetime | None = None,
) -> None:
    """独立会话写入缓存并回写历史会话名；查无只记 details_missed_at，不清掉已缓存的详情。"""
    now = fetched_at or now_naive()
    db = SessionLocal()
    try:
        row = db.get(SteamApp, app_id)
        if row is None:
            row = SteamApp(app_id=app_id, fetched_at=now)
            db.add(row)
        if details.success:
            _apply_details(row, details, now)
            row.details_missed_at = None
        else:
            row.details_missed_at = now

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
        clear_log_until_change("steam-app-cache")
    except SQLAlchemyError as exc:
        db.rollback()
        log_until_change(
            logger,
            "steam-app-cache",
            "persist steam app cache failed for %s: %s",
            app_id,
            type(exc).__name__,
        )
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
    now = now_naive()
    result: dict[str, str] = {}

    for app_id in ids:
        row = by_id.get(app_id)
        if row and row.name:
            result[app_id] = row.name
            continue
        if row and _name_cache_fresh(row, now):
            continue
        if not fetch_missing or not is_valid_app_id(app_id):
            continue

        details = fetch_store_details(app_id)
        _persist_store_row(app_id, details, fetched_at=now)
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
) -> dict[str, str]:
    """批量读库：AppID → 库列表小图标 URL（不含商店 capsule/header）；缺的由 fetch_app_icon 单个补。"""
    ids = sorted({str(a).strip() for a in app_ids if a and str(a).strip()})
    if not ids:
        return {}

    rows = db.query(SteamApp).filter(SteamApp.app_id.in_(ids)).all()
    result: dict[str, str] = {}
    for row in rows:
        icon = (row.icon_url or "").strip()
        # 丢掉误写入的非 client icon
        if _is_client_icon_url(icon):
            result[row.app_id] = icon
    return result


def fetch_app_icon(db: Session, app_id: str) -> str | None:
    """单个 AppID 的库列表小图标：先读库；没有且不在查无重试窗口内才回源（同 id 并发只回源一次）。

    调用方须先用 is_known_app 挡掉站内没出现过的 id。
    """
    row = db.get(SteamApp, app_id)
    if row is not None:
        if _is_client_icon_url(row.icon_url):
            return row.icon_url
        if _missed_recently(row.icon_missed_at, _ICON_MISS_RETRY, now_naive()):
            return None
    # 回源慢：先结束读事务把连接还给池；等别人回源完，新事务才读得到对方刚提交的结果
    db.commit()
    with _single_flight(f"icon:{app_id}") as leader:
        row = db.get(SteamApp, app_id)
        if row is not None:
            if _is_client_icon_url(row.icon_url):
                return row.icon_url
            if _missed_recently(row.icon_missed_at, _ICON_MISS_RETRY, now_naive()):
                return None
        if not leader:
            return None
        url = _backfill_client_icon(db, app_id)
        _store_icon_result(db, app_id, url)
        return url


def _candidate_steam_ids_for_icons(db: Session, app_id: str) -> list[str]:
    """玩过该游戏的成员（多半拥有它）；没人玩过就不拿别人的库碰运气。"""
    from app.models.member import Member

    rows = (
        db.query(Member.steam_id)
        .join(PlaySession, PlaySession.member_id == Member.id)
        .filter(
            Member.steam_id.isnot(None),
            Member.steam_id != "",
            PlaySession.steam_app_id == app_id,
        )
        .distinct()
        .limit(_OWNED_GAMES_CALLS_MAX)
        .all()
    )
    return [str(sid).strip() for (sid,) in rows if sid and str(sid).strip()]


def _client_icon_cdn_url(app_id: str, icon_hash: str) -> str:
    return (
        "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/"
        f"apps/{app_id}/{icon_hash}.jpg"
    )


def _fetch_icon_hash_from_steamcmd(app_id: str) -> str | None:
    """从 steamcmd 公开 appinfo 取库列表 icon hash（无需 Steam API Key / 游戏库）。"""
    app_id = str(app_id).strip()
    if not is_valid_app_id(app_id):
        return None
    url = f"https://api.steamcmd.net/v1/info/{app_id}"
    try:
        resp = http_request(
            "GET", url, headers={"User-Agent": _UA}, timeout=15
        )
        payload = resp.json()
    except (HttpRequestError, ValueError, OSError) as exc:
        logger.debug("steamcmd appinfo failed for %s: %s", app_id, exc)
        return None
    if resp.status_code >= 400 or not isinstance(payload, dict):
        logger.debug("steamcmd appinfo failed for %s: HTTP %s", app_id, resp.status_code)
        return None

    data = payload.get("data")
    entry = data.get(app_id) if isinstance(data, dict) else None
    common = entry.get("common") if isinstance(entry, dict) else None
    if not isinstance(common, dict):
        return None
    icon_hash = str(common.get("icon") or "").strip().lower()
    if re.fullmatch(r"[a-f0-9]{40}", icon_hash):
        return icon_hash
    return None


def _backfill_client_icon(db: Session, app_id: str) -> str | None:
    """先查玩过该游戏的成员库（最多 _OWNED_GAMES_CALLS_MAX 次 GetOwnedGames），仍缺再查 steamcmd 公开 appinfo。

    与是否开启假监控无关——假监控只伪造用户在线/游玩状态。
    """
    from app.services.adapters.steam import SteamAdapter
    from app.services.integrations_config import get_steam_api_key

    steam_key = get_steam_api_key(db)
    steam_ids = _candidate_steam_ids_for_icons(db, app_id) if steam_key else []
    db.commit()
    if steam_ids:
        adapter = SteamAdapter(steam_key)
        for steam_id in steam_ids:
            try:
                icons = adapter.fetch_owned_game_icons(steam_id)
            except RuntimeError as exc:
                log_until_change(
                    logger, "steam-icon:owned-games", "GetOwnedGames for client icons failed: %s", exc
                )
                break
            clear_log_until_change("steam-icon:owned-games")
            url = icons.get(app_id)
            if url and _http_url_ok(url):
                return url
    icon_hash = _fetch_icon_hash_from_steamcmd(app_id)
    if icon_hash:
        url = _client_icon_cdn_url(app_id, icon_hash)
        if _http_url_ok(url):
            return url
    return None


def _store_icon_result(db: Session, app_id: str, url: str | None) -> None:
    """补到就写 icon_url；各渠道都没有就记 icon_missed_at，重试窗口内不再回源。"""
    now = now_naive()
    try:
        row = db.get(SteamApp, app_id)
        if row is None:
            row = SteamApp(app_id=app_id, fetched_at=now)
            db.add(row)
        if url:
            row.icon_url = url
            row.icon_missed_at = None
        else:
            row.icon_missed_at = now
        db.commit()
        clear_log_until_change("steam-app-cache")
    except SQLAlchemyError as exc:
        db.rollback()
        log_until_change(
            logger,
            "steam-app-cache",
            "persist steam client icon failed for %s: %s",
            app_id,
            type(exc).__name__,
        )


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


def _cached_store_card(row: SteamApp | None) -> dict[str, Any] | None:
    # 没头图的卡片前端只能一直显示「加载中」，按查无处理
    if row is None or not row.header_image:
        return None
    card = _serialize_store_card(row)
    if not _is_client_icon_url(card.get("icon_url")):
        card["icon_url"] = None
    return card


def _store_card_settled(row: SteamApp | None, now: datetime) -> bool:
    return row is not None and (
        _details_fresh(row, now)
        or _missed_recently(row.details_missed_at, _DETAILS_MISS_RETRY, now)
    )


def get_store_card(db: Session, app_id: str) -> dict[str, Any] | None:
    """返回商店悬停卡片数据；按 TTL 刷新价格与头图，查无后重试窗口内不再回源（同 id 并发只回源一次）。

    调用方须先用 is_known_app 挡掉站内没出现过的 id。
    """
    app_id = str(app_id).strip()
    if not is_valid_app_id(app_id):
        return None

    now = now_naive()
    row = db.get(SteamApp, app_id)
    if _store_card_settled(row, now):
        return _cached_store_card(row)
    db.commit()
    with _single_flight(f"details:{app_id}") as leader:
        row = db.get(SteamApp, app_id)
        if not leader or _store_card_settled(row, now):
            return _cached_store_card(row)
        icon_url = row.icon_url if row is not None else None
        details = fetch_store_details(app_id)
        _persist_store_row(app_id, details, fetched_at=now)
    if not details.success:
        # 查无只记时间，旧详情仍可展示
        return _cached_store_card(row)
    card = {
        "steam_app_id": app_id,
        "name": details.name or (row.name if row else None),
        "header_image": details.header_image,
        "capsule_image": details.capsule_image,
        "icon_url": icon_url if _is_client_icon_url(icon_url) else None,
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
    return card if card["header_image"] else None
