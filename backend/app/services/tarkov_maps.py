"""逃离塔科夫地图：读 bosses maps raw 投影目录/详情（不另存一份）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov_bosses import (
    TarkovBossesError,
    _as_int,
    _locale_lookup,
    _map_zh,
    _maps_blob,
    _mob_name,
    _mobs_blob,
    ensure_bosses,
    get_bosses_raw,
)
from app.services.tarkov_bosses import _load_payload as load_bosses_payload

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
    slug = (normalized or "").strip()
    if not slug:
        return ""
    return f"https://tarkov.dev/maps/{slug}_thumb.jpg"


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
        out.append(
            {
                "id": ident,
                "name": label,
                "faction": _faction_label(str(row.get("faction") or "")),
            }
        )
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
            }
        )
    out.sort(key=lambda r: (-int(r.get("spawn_chance") or 0), str(r.get("name") or "")))
    return out


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
    return {
        **row,
        "variants": variants,
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }
