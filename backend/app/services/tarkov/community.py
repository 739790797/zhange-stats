"""工作台社区方案：按枪按需读 EFTForge 公开列表。

只 GET `/builds/public`。不当图鉴源、不落库、不代投票/评论、不热链对方卡图。
短时 KV 缓存原始 JSON，投影时用本站 dump 丢掉装不上的 pairs。
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ephemeral_kv import ephemeral_get, ephemeral_set
from app.core.http_client import HttpRequestError, http_request
from app.services.tarkov import workbench as workbench_svc
from app.services.tarkov.http import DEFAULT_UA
from app.services.tarkov.workbench import WbItem, WorkbenchIndex

SOURCE_NAME = "EFTForge"
SOURCE_URL = "https://eftforge.com/"
CACHE_TTL_SEC = 300
MAX_BUILDS = 400
MAX_PAIRS = 200
MAX_RAW_BYTES = 2_000_000
EFTFORGE_HOSTS = frozenset({"eftforge.com", "www.eftforge.com"})
ALLOWED_TAGS = frozenset(
    {
        "meta",
        "budget",
        "cqb",
        "sniper",
        "recoil",
        "ergo",
        "pve",
        "beginner",
        "hybrid",
    }
)


class TarkovCommunityError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _cache_key(gun_id: str) -> str:
    return f"tarkov:eftforge:public:{gun_id}"


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit]


def parse_raw_pairs(raw: Any) -> list[tuple[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, str]] = []
    for row in raw[:MAX_PAIRS]:
        slot_id = ""
        item_id = ""
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            slot_id = str(row[0] or "").strip()
            item_id = str(row[1] or "").strip()
        elif isinstance(row, dict):
            slot_id = str(row.get("slot_id") or "").strip()
            item_id = str(row.get("item_id") or "").strip()
        if slot_id and item_id:
            out.append((slot_id, item_id))
    return out


def parse_tags(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        tag = str(item or "").strip().lower()
        if tag not in ALLOWED_TAGS or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= 5:
            break
    return out


def author_name(row: dict[str, Any]) -> str:
    if row.get("is_admin_build"):
        return _clip(
            row.get("author_display_name_zh")
            or row.get("author_display_name")
            or "Morph1ne",
            30,
        )
    return _clip(row.get("user_display_name") or "匿名", 30)


def preview_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
    ergo = _as_float(stats.get("ergo")) if stats else None
    evo = _as_float(stats.get("eed")) if stats else None
    recoil_v = _as_int(stats.get("recoil_v")) if stats else None
    recoil_h = _as_int(stats.get("recoil_h")) if stats else None
    weight = _as_float(stats.get("weight")) if stats else None
    price = _as_int(row.get("total_price_rub"))
    overswing = bool(stats.get("overswing")) if stats else False
    if (
        ergo is None
        and evo is None
        and recoil_v is None
        and recoil_h is None
        and weight is None
        and price is None
        and not overswing
    ):
        return None
    return {
        "ergonomics": ergo,
        "evo_ergo_delta": evo,
        "recoil_vertical": recoil_v,
        "recoil_horizontal": recoil_h,
        "weight": weight,
        "price_rub": price,
        "overswing": overswing,
    }


def project_public_build(
    index: WorkbenchIndex,
    gun: WbItem,
    row: Any,
) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    ident = str(row.get("id") or "").strip()
    if not ident:
        return None
    row_gun = str(row.get("gun_id") or "").strip()
    if row_gun and row_gun != gun.id:
        return None
    raw_pairs = parse_raw_pairs(row.get("pairs"))
    pairs = workbench_svc.compatible_pairs(index, gun, raw_pairs)
    dropped = max(0, len(workbench_svc._pairs_map(raw_pairs)) - len(pairs))
    name = _clip(row.get("build_name"), 60) or "未命名方案"
    loadable = bool(pairs)
    return {
        "id": ident[:64],
        "name": name,
        "author": author_name(row),
        "featured": bool(row.get("is_featured")),
        "tags": parse_tags(row.get("tags")),
        "published_at": _clip(row.get("published_at"), 40) or None,
        "load_count": max(0, _as_int(row.get("load_count"), 0) or 0),
        "ammo_id": workbench_svc.compatible_ammo_id(gun, str(row.get("ammo_id") or "")),
        "pairs": [{"slot_id": slot, "item_id": item} for slot, item in pairs],
        "loadable": loadable,
        "dropped_pair_count": dropped,
        "preview": preview_from_row(row),
    }


def _decode_public_payload(raw: bytes) -> list[Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovCommunityError("社区方案数据无法解析") from exc
    if isinstance(data, list):
        return data
    raise TarkovCommunityError("社区方案数据格式不对")


def public_builds_request_url(gun_id: str, base_url: str | None = None) -> str:
    base = str(base_url or SOURCE_URL).strip().rstrip("/")
    return f"{base}/builds/public?{urlencode({'gun_id': gun_id})}"


def accept_eftforge_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host not in EFTFORGE_HOSTS:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    path = (parsed.path or "").rstrip("/") or "/"
    return path == "/builds/public"


def _header(headers: Any, name: str) -> str:
    if headers is None or not hasattr(headers, "get"):
        return ""
    for key in (name, name.lower(), name.title()):
        value = headers.get(key)
        if value:
            return str(value).strip()
    return ""


def _get_public(url: str) -> Any:
    try:
        return http_request(
            "GET",
            url,
            headers={"User-Agent": DEFAULT_UA, "Accept": "application/json"},
            timeout=20,
            follow_redirects=False,
        )
    except HttpRequestError as exc:
        raise TarkovCommunityError("无法连接社区方案源") from exc


def _redirect_location(url: str, resp: Any) -> str | None:
    """3xx 返回跳转目标；非跳转返回 None。空 Location 返回空串。"""
    status = int(getattr(resp, "status_code", 0) or 0)
    if not (300 <= status < 400):
        return None
    location = _header(getattr(resp, "headers", None), "location")
    if not location:
        return ""
    return urljoin(url, location)


def fetch_public_raw(gun_id: str) -> list[Any]:
    ident = (gun_id or "").strip()
    if not ident:
        raise TarkovCommunityError("未找到枪械", status_code=404)
    cached = ephemeral_get(_cache_key(ident))
    if cached:
        try:
            data = json.loads(cached)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return data
    settings = get_settings()
    url = public_builds_request_url(ident, settings.EFTFORGE_BASE_URL)
    if not accept_eftforge_public_url(url):
        raise TarkovCommunityError("社区方案源未配置", status_code=503)
    resp = _get_public(url)
    hop = _redirect_location(url, resp)
    if hop is not None:
        # 对方 apex 会 301 到 www；只跟一跳，且目标仍须是白名单公开列表。
        if not hop or not accept_eftforge_public_url(hop):
            raise TarkovCommunityError("社区方案源异常跳转", status_code=502)
        resp = _get_public(hop)
        if _redirect_location(hop, resp) is not None:
            raise TarkovCommunityError("社区方案源异常跳转", status_code=502)
    if resp.status_code == 403:
        detail = ""
        try:
            payload = json.loads(resp.content.decode("utf-8", errors="replace"))
            detail = str(payload.get("detail") or "")
        except Exception:  # noqa: BLE001
            detail = ""
        if "community_builds_disabled" in detail:
            raise TarkovCommunityError("对方已关闭社区方案", status_code=503)
        raise TarkovCommunityError("社区方案暂不可用", status_code=503)
    if resp.status_code >= 400:
        raise TarkovCommunityError("社区方案源失败", status_code=502)
    if len(resp.content) > MAX_RAW_BYTES:
        raise TarkovCommunityError("社区方案数据过大", status_code=502)
    rows = _decode_public_payload(resp.content)
    ephemeral_set(
        _cache_key(ident),
        json.dumps(rows[:MAX_BUILDS], ensure_ascii=False),
        ttl_sec=CACHE_TTL_SEC,
    )
    return rows


def list_public_builds(db: Session, gun_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.TARKOV_WORKBENCH_COMMUNITY:
        raise TarkovCommunityError("社区方案未开启", status_code=503)
    index = workbench_svc.load_index(db)
    gun = workbench_svc._require_gun(index, gun_id)
    rows = fetch_public_raw(gun.id)
    builds: list[dict[str, Any]] = []
    for row in rows[:MAX_BUILDS]:
        projected = project_public_build(index, gun, row)
        if projected:
            builds.append(projected)
    builds.sort(key=lambda row: row.get("published_at") or "", reverse=True)
    builds.sort(key=lambda row: 0 if row.get("featured") else 1)
    return {
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "gun_id": gun.id,
        "builds": builds,
    }
