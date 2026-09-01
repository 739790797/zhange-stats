"""三狗社区位置：读 Tarkov Stammtisch 聚合接口，进程内缓存并推送。"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any

from app.services.tarkov.bosses import MAP_ZH
from app.services.tarkov.game_mode import parse_game_mode
from app.services.tarkov.goon_tracker_hub import hub
from app.services.tarkov.http import download_bytes

logger = logging.getLogger(__name__)

SOURCE = "tarkov-stammtisch"
SOURCE_HOST = "https://tarkov-stammtisch.de"
BUNDLE_URL = f"{SOURCE_HOST}/api/tarkov/goons"
SOURCE_URL = f"{SOURCE_HOST}/en/tarkov/goon-tracker"
GOON_MAP_SLUGS = ("woods", "shoreline", "customs", "lighthouse")
GOON_MAP_SET = frozenset(GOON_MAP_SLUGS)
MAP_ENGLISH = {
    "woods": "Woods",
    "shoreline": "Shoreline",
    "customs": "Customs",
    "lighthouse": "Lighthouse",
}
MAP_SLUG_ALIASES = {
    "bigmap": "customs",
    "wood": "woods",
    "the-woods": "woods",
    "shore": "shoreline",
    "light-house": "lighthouse",
}
ISO_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
POLL_SEC = 60
FETCH_TIMEOUT = 12


class GoonTrackerError(Exception):
    """上游拉取或解析失败。"""


_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}
_fingerprints: dict[str, str] = {}
_stop = threading.Event()
_thread: threading.Thread | None = None


def source_url(mode: str | None = None) -> str:
    _ = parse_game_mode(mode)
    return SOURCE_URL


def empty_status(mode: str | None = None) -> dict[str, Any]:
    parsed = parse_game_mode(mode)
    return {
        "game_mode": parsed,
        "map_slug": "",
        "map_name": "",
        "map_english": "",
        "seen_at": None,
        "report_id": "",
        "source": SOURCE,
        "source_url": source_url(parsed),
    }


def normalize_goon_map_slug(raw: Any) -> str:
    text = str(raw or "").strip().lower().replace("_", "-").replace(" ", "-")
    if not text:
        return ""
    text = MAP_SLUG_ALIASES.get(text, text)
    return text if text in GOON_MAP_SET else ""


def status_fingerprint(status: dict[str, Any] | None) -> str:
    if not status:
        return ""
    return "|".join(
        (
            str(status.get("report_id") or ""),
            str(status.get("map_slug") or ""),
            str(status.get("seen_at") or ""),
        )
    )


def project_status(tracking: dict[str, Any] | None, mode: str | None = None) -> dict[str, Any]:
    parsed = parse_game_mode(mode)
    base = empty_status(parsed)
    if not tracking:
        return base
    slug = normalize_goon_map_slug(_tracking_map_slug(tracking))
    seen_at = _normalize_iso(_tracking_seen_at(tracking))
    if not slug or not seen_at:
        return base
    report_id = str(tracking.get("id") or tracking.get("report_id") or seen_at)
    return {
        **base,
        "map_slug": slug,
        "map_name": MAP_ZH.get(slug, slug),
        "map_english": MAP_ENGLISH.get(slug, slug),
        "seen_at": seen_at,
        "report_id": report_id,
    }


def parse_stammtisch_bundle(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        return {"pvp": [], "pve": []}
    return {
        "pvp": _parse_sighting_list(payload.get("pvp")),
        "pve": _parse_sighting_list(payload.get("pve")),
    }


def pick_latest_tracking(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_key = ""
    for row in rows:
        slug = normalize_goon_map_slug(_tracking_map_slug(row))
        seen_at = _normalize_iso(_tracking_seen_at(row))
        if not slug or not seen_at:
            continue
        if seen_at > best_key:
            best = {**row, "id": str(row.get("id") or seen_at)}
            best_key = seen_at
    return best


def get_cached(mode: str | None = None) -> dict[str, Any]:
    parsed = parse_game_mode(mode)
    with _lock:
        cached = _cache.get(parsed)
        if cached:
            return dict(cached)
    return empty_status(parsed)


def get_status(mode: str | None = None) -> dict[str, Any]:
    parsed = parse_game_mode(mode)
    with _lock:
        if parsed in _cache:
            return dict(_cache[parsed])
    refresh_all()
    return get_cached(parsed)


def refresh_mode(mode: str) -> bool:
    refresh_all()
    parsed = parse_game_mode(mode)
    with _lock:
        return parsed in _cache


def refresh_all() -> list[str]:
    try:
        bundle = _fetch_bundle()
    except GoonTrackerError:
        logger.warning("goon tracker fetch failed", exc_info=True)
        return []
    changed: list[str] = []
    for mode in ("pvp", "pve"):
        tracking = pick_latest_tracking(bundle.get(mode) or [])
        if _store_status(mode, project_status(tracking, mode)):
            changed.append(mode)
    if changed:
        hub.publish(_snapshot_payload())
    return changed


def snapshot_payload() -> dict[str, Any]:
    return _snapshot_payload()


def start_poller() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_poll_loop,
        name="tarkov-goon-tracker",
        daemon=True,
    )
    _thread.start()


def stop_poller(*, timeout: float = 2.0) -> None:
    global _thread
    _stop.set()
    thread = _thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)
    _thread = None


def reset_cache_for_tests() -> None:
    with _lock:
        _cache.clear()
        _fingerprints.clear()


def _snapshot_payload() -> dict[str, Any]:
    return {
        "event": "goons",
        "pvp": get_cached("pvp"),
        "pve": get_cached("pve"),
    }


def _poll_loop() -> None:
    while True:
        try:
            refresh_all()
        except Exception:  # noqa: BLE001
            logger.exception("goon tracker poll failed")
        if _stop.wait(POLL_SEC):
            break


def _fetch_bundle() -> dict[str, list[dict[str, Any]]]:
    raw = download_bytes(
        BUNDLE_URL,
        headers={"Accept": "application/json"},
        timeout=FETCH_TIMEOUT,
        error_cls=GoonTrackerError,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise GoonTrackerError("Stammtisch 响应无效") from exc
    return parse_stammtisch_bundle(payload)


def _store_status(mode: str, status: dict[str, Any]) -> bool:
    parsed = parse_game_mode(mode)
    fingerprint = status_fingerprint(status)
    with _lock:
        prev = _fingerprints.get(parsed)
        if fingerprint == prev and parsed in _cache:
            return False
        if not status.get("map_slug") and prev:
            return False
        _cache[parsed] = status
        _fingerprints[parsed] = fingerprint
    return fingerprint != prev


def _parse_sighting_list(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        parsed = _parse_stammtisch_sighting(row)
        if parsed:
            out.append(parsed)
    return out


def _parse_stammtisch_sighting(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    mapped = row.get("map") if isinstance(row.get("map"), dict) else {}
    slug = str(
        mapped.get("normalizedName") or mapped.get("slug") or mapped.get("name") or ""
    )
    seen = str(row.get("timestamp") or row.get("currentDate") or "")
    origin = str(row.get("externalSource") or row.get("source") or "")
    username = str(row.get("username") or "")
    report_id = "|".join(part for part in (seen, slug, origin, username) if part)
    if not seen and not slug:
        return None
    return {
        "id": report_id or seen,
        "currentDate": seen,
        "map": {"slug": slug, "name": str(mapped.get("name") or slug)},
        "origin": origin,
    }


def _tracking_map_slug(tracking: dict[str, Any]) -> str:
    mapped = tracking.get("map")
    if isinstance(mapped, dict):
        return str(
            mapped.get("slug")
            or mapped.get("normalizedName")
            or mapped.get("name")
            or ""
        )
    return str(tracking.get("map_slug") or "")


def _tracking_seen_at(tracking: dict[str, Any]) -> str:
    return str(
        tracking.get("currentDate")
        or tracking.get("timestamp")
        or tracking.get("seen_at")
        or ""
    )


def _normalize_iso(raw: str) -> str:
    text = str(raw or "").strip()
    if not ISO_PREFIX.match(text):
        return ""
    if text.endswith("Z") or "+" in text[10:] or text.endswith("z"):
        stamp = text.replace("z", "Z")
        try:
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return ""
        if stamp.endswith("Z") and "." not in stamp:
            return stamp
        try:
            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
