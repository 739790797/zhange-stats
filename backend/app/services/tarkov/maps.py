"""逃离塔科夫地图：读 bosses maps raw 投影目录/详情（不另存一份）。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov.ammo import TARKOV_GRAPHQL_URL
from app.services.tarkov.bosses import (
    TarkovBossesError,
    _as_int,
    _http_request,
    _locale_lookup,
    _map_zh,
    _maps_blob,
    _mob_name,
    _mobs_blob,
    map_xyz,
    ensure_bosses,
    get_bosses_raw,
)
from app.services.tarkov.bosses import _load_payload as load_bosses_payload

logger = logging.getLogger(__name__)

MAPS_PAGE_SIZE_DEFAULT = 50

# 首页 / 顶栏短 id → json.tarkov.dev normalizedName
SLUG_ALIASES: dict[str, str] = {
    "lab": "the-lab",
    "streets": "streets-of-tarkov",
    "labyrinth": "the-labyrinth",
    "the-labyrinth": "the-labyrinth",
    "night-factory": "night-factory",
    "factory-night": "night-factory",
}

VARIANT_PARENT: dict[str, str] = {
    "night-factory": "factory",
    "the-lab-dark": "the-lab",
    "ground-zero-21": "ground-zero",
    "ground-zero-tutorial": "ground-zero",
}

HUB_SKIP = {"ground-zero-tutorial", "openworld", "transits"}

_MARKERS_QUERY = """
query MapMarkers($lang: LanguageCode) {
  maps(lang: $lang) {
    normalizedName
    extracts {
      id
      name
      faction
      position { x y z }
    }
    bosses {
      normalizedName
      spawnLocations {
        name
        chance
        positions { x y z }
      }
    }
  }
}
""".strip()

_MARKER_TTL_SEC = 3600
_marker_cache: dict[str, Any] = {"at": 0.0, "by_slug": {}}

# tarkov.dev /maps/{slug}_thumb.jpg 已被 SPA 路由吞成 HTML；改用 assets 上的 svg/瓦片。
MAP_THUMB_ASSETS: dict[str, str] = {
    "customs": "https://assets.tarkov.dev/maps/svg/Customs.svg",
    "factory": "https://assets.tarkov.dev/maps/svg/Factory.svg",
    "ground-zero": "https://assets.tarkov.dev/maps/svg/GroundZero.svg",
    "interchange": "https://assets.tarkov.dev/maps/svg/Interchange.svg",
    "lighthouse": "https://assets.tarkov.dev/maps/svg/Lighthouse.svg",
    "reserve": "https://assets.tarkov.dev/maps/svg/Reserve.svg",
    "shoreline": "https://assets.tarkov.dev/maps/svg/Shoreline.svg",
    "streets-of-tarkov": "https://assets.tarkov.dev/maps/svg/StreetsOfTarkov.svg",
    "terminal": "https://assets.tarkov.dev/maps/svg/Terminal.svg",
    "woods": "https://assets.tarkov.dev/maps/svg/Woods.svg",
    "the-lab": "https://assets.tarkov.dev/maps/labs_v4/1st/0/0/0.png",
    "the-labyrinth": "https://assets.tarkov.dev/maps/labyrinth/main/0/0/0.png",
    "icebreaker": "https://assets.tarkov.dev/maps/icebreaker/06_infirmary/0/0/0.png",
}


def resolve_map_slug(slug: str) -> str:
    key = (slug or "").strip().lower()
    return SLUG_ALIASES.get(key, key)


def _faction_label(raw: str) -> str:
    key = (raw or "").strip().lower()
    return {
        "pmc": "PMC",
        "scav": "Scav",
        "shared": "通用",
        "all": "通用",
        "any": "通用",
    }.get(key, raw or "—")


def _thumb_url(normalized: str) -> str:
    slug = resolve_map_slug(normalized)
    if not slug:
        return ""
    slug = VARIANT_PARENT.get(slug, slug)
    if slug in MAP_THUMB_ASSETS:
        return MAP_THUMB_ASSETS[slug]
    pascal = "".join(part.capitalize() for part in slug.split("-") if part)
    if not pascal:
        return ""
    return f"https://assets.tarkov.dev/maps/svg/{pascal}.svg"


def _interactive_url(normalized: str) -> str:
    slug = (normalized or "").strip()
    if not slug:
        return ""
    return f"https://tarkov.dev/map/{slug}"


def _extracts(raw: dict[str, Any], locale: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw.get("extracts") or []:
        if not isinstance(row, dict):
            continue
        ident = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        loc = _locale_lookup(locale, name, ident) if name else ""
        label = loc or name or ident
        if not label or label in seen:
            continue
        seen.add(label)
        item: dict[str, Any] = {
            "id": ident,
            "name": label,
            "faction": _faction_label(str(row.get("faction") or "")),
        }
        point = map_xyz(row)
        if point:
            item["x"] = point["x"]
            item["y"] = point["y"]
            item["z"] = point["z"]
        out.append(item)
    out.sort(key=lambda r: (r.get("faction") or "", r.get("name") or ""))
    return out


def _map_bosses(
    raw: dict[str, Any],
    mobs: dict[str, dict[str, Any]],
    locale: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spawn in raw.get("bosses") or []:
        if not isinstance(spawn, dict):
            continue
        mob_id = str(spawn.get("mob") or spawn.get("id") or "").strip()
        if not mob_id or mob_id in seen:
            continue
        seen.add(mob_id)
        mob = mobs.get(mob_id) if isinstance(mobs.get(mob_id), dict) else {}
        slug = str((mob or {}).get("normalizedName") or "").strip()
        chance = float(spawn.get("spawnChance") or 0)
        out.append(
            {
                "id": mob_id,
                "slug": slug,
                "name": _mob_name(mob_id, mob or {}, locale),
                "spawn_chance": round(chance * 100) if chance <= 1 else int(chance),
                "locations": _boss_locations(spawn, locale),
            }
        )
    out.sort(key=lambda r: (-int(r.get("spawn_chance") or 0), str(r.get("name") or "")))
    return out


def _boss_locations(spawn: dict[str, Any], locale: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for loc in spawn.get("spawnLocations") or []:
        if not isinstance(loc, dict):
            continue
        key = str(loc.get("spawnKey") or loc.get("name") or "").strip()
        name = _locale_lookup(locale, key) if key else ""
        label = name or str(loc.get("name") or key)
        positions: list[dict[str, float]] = []
        for raw in loc.get("positions") or []:
            point = map_xyz(raw)
            if point:
                positions.append(point)
        if not positions:
            point = map_xyz(loc)
            if point:
                positions.append(point)
        chance = float(loc.get("chance") or 0)
        out.append({"name": label, "chance": chance, "positions": positions})
    return out


def _extracts_have_coords(extracts: list[dict[str, Any]]) -> bool:
    return any(row.get("x") is not None and row.get("z") is not None for row in extracts)


def _graphql_map_markers(*, lang: str = "zh") -> dict[str, dict[str, Any]]:
    now = time.time()
    cached = _marker_cache.get("by_slug")
    if isinstance(cached, dict) and cached and now - float(_marker_cache.get("at") or 0) < _MARKER_TTL_SEC:
        return cached
    body = json.dumps(
        {"query": _MARKERS_QUERY, "variables": {"lang": lang}},
        ensure_ascii=False,
    ).encode("utf-8")
    raw = _http_request(
        TARKOV_GRAPHQL_URL,
        method="POST",
        body=body,
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("errors"):
        raise TarkovBossesError(f"tarkov.dev GraphQL 错误: {payload.get('errors')}")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("maps") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise TarkovBossesError("tarkov.dev maps 标记响应无效")
    by_slug: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("normalizedName") or "").strip()
        if slug:
            by_slug[slug] = row
    _marker_cache["at"] = now
    _marker_cache["by_slug"] = by_slug
    return by_slug


def _apply_graphql_markers(
    row: dict[str, Any],
    locale: dict[str, Any] | None = None,
) -> None:
    extracts = row.get("extracts") if isinstance(row.get("extracts"), list) else []
    if _extracts_have_coords(extracts):
        return
    try:
        by_slug = _graphql_map_markers()
    except Exception:  # noqa: BLE001
        logger.warning("tarkov.dev GraphQL map markers unavailable", exc_info=True)
        return
    extra = by_slug.get(str(row.get("slug") or "")) or by_slug.get(str(row.get("id") or ""))
    if not extra:
        return
    gql_extracts = extra.get("extracts") if isinstance(extra.get("extracts"), list) else []
    by_id = {
        str(item.get("id") or ""): item
        for item in gql_extracts
        if isinstance(item, dict) and item.get("id")
    }
    by_name = {
        str(item.get("name") or ""): item
        for item in gql_extracts
        if isinstance(item, dict) and item.get("name")
    }
    for extract in extracts:
        if extract.get("x") is not None and extract.get("z") is not None:
            continue
        src = by_id.get(str(extract.get("id") or "")) or by_name.get(
            str(extract.get("name") or "")
        )
        point = map_xyz(src) if src else None
        if not point:
            continue
        extract["x"] = point["x"]
        extract["y"] = point["y"]
        extract["z"] = point["z"]
    gql_bosses = extra.get("bosses") if isinstance(extra.get("bosses"), list) else []
    gql_by_slug = {
        str(item.get("normalizedName") or ""): item
        for item in gql_bosses
        if isinstance(item, dict) and item.get("normalizedName")
    }
    for boss in row.get("bosses") or []:
        if not isinstance(boss, dict):
            continue
        locs = boss.get("locations") if isinstance(boss.get("locations"), list) else []
        if any(loc.get("positions") for loc in locs if isinstance(loc, dict)):
            continue
        src = gql_by_slug.get(str(boss.get("slug") or ""))
        if not src:
            continue
        boss["locations"] = _boss_locations(src, locale or {})


def parse_map_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locale = payload.get("locale") if isinstance(payload.get("locale"), dict) else {}
    maps = _maps_blob(payload)
    mobs = _mobs_blob(payload)
    rows: list[dict[str, Any]] = []
    for key, raw in maps.items():
        if not isinstance(raw, dict):
            continue
        slug = str(raw.get("normalizedName") or key or "").strip()
        if not slug:
            continue
        duration = _as_int(raw.get("raidDuration"), 0) or 0
        rows.append(
            {
                "id": str(raw.get("id") or key),
                "slug": slug,
                "name": _map_zh(raw, locale),
                "english": slug.replace("-", " ").title(),
                "description": _locale_lookup(
                    locale,
                    f"{raw.get('id')} Description",
                    str(raw.get("description") or ""),
                )
                or "",
                "wiki_link": str(raw.get("wiki") or ""),
                "raid_duration": duration,
                "players": str(raw.get("players") or ""),
                "min_player_level": _as_int(raw.get("minPlayerLevel"), 0) or 0,
                "max_player_level": _as_int(raw.get("maxPlayerLevel"), 0) or 0,
                "thumb_link": _thumb_url(slug),
                "interactive_url": _interactive_url(slug),
                "parent_slug": VARIANT_PARENT.get(slug, ""),
                "extracts": _extracts(raw, locale),
                "bosses": _map_bosses(raw, mobs, locale),
            }
        )
    rows.sort(key=lambda r: (str(r.get("name") or ""), str(r.get("slug") or "")))
    return rows


def _find_map(rows: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
    key = resolve_map_slug(slug)
    if not key:
        return None
    for row in rows:
        if str(row.get("slug") or "") == key:
            return row
    lowered = key.lower()
    for row in rows:
        if str(row.get("id") or "").lower() == lowered:
            return row
        if str(row.get("slug") or "").replace("-", "") == lowered.replace("-", ""):
            return row
    return None


_HUB_FIELDS = (
    "id",
    "slug",
    "name",
    "english",
    "raid_duration",
    "players",
    "thumb_link",
    "interactive_url",
    "parent_slug",
    "min_player_level",
    "max_player_level",
)


def list_maps(db: Session) -> dict[str, Any]:
    if get_bosses_raw(db) is None:
        ensure_bosses(db)
    source, payload, synced_at, note = load_bosses_payload(db)
    rows = parse_map_rows(payload)
    hub = [
        {key: r.get(key) for key in _HUB_FIELDS}
        for r in rows
        if r.get("slug") not in HUB_SKIP and not r.get("parent_slug")
    ]
    return {
        "items": hub,
        "map_count": len(hub),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def get_map_detail(db: Session, slug: str) -> dict[str, Any]:
    key = resolve_map_slug(slug)
    if not key:
        raise TarkovBossesError("地图 slug 无效")
    if get_bosses_raw(db) is None:
        ensure_bosses(db)
    source, payload, synced_at, note = load_bosses_payload(db)
    rows = parse_map_rows(payload)
    row = _find_map(rows, key)
    if row is None:
        raise TarkovBossesError(f"未找到地图: {slug}")
    parent = row.get("parent_slug") or row.get("slug")
    variants = [
        {
            "slug": v.get("slug") or "",
            "name": v.get("name") or "",
            "raid_duration": v.get("raid_duration") or 0,
            "players": v.get("players") or "",
        }
        for v in rows
        if v.get("parent_slug") == parent and v.get("slug") != row.get("slug")
    ]
    locale = payload.get("locale") if isinstance(payload.get("locale"), dict) else {}
    _apply_graphql_markers(row, locale)
    return {
        **row,
        "variants": variants,
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }
