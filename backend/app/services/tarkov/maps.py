"""逃离塔科夫地图：读 tarkov_maps_raws 投影目录/详情（不另存一份）。"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov.game_mode import parse_game_mode
from app.services.tarkov.bosses import (
    TarkovBossesError,
    _as_int,
    _locale_lookup,
    _map_zh,
    _maps_blob,
    _mob_name,
    _mobs_blob,
    _spawn_mobs,
    assign_boss_slugs,
    classify_boss_kind,
    map_xyz,
    ensure_maps,
    get_maps_raw,
)
from app.services.tarkov.bosses import _load_payload as load_maps_payload

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

# 对齐 tarkov.dev map/index.jsx Spawns：PMC / Scav / 狙击 Scav（Boss 用 bosses.locations）。
SPAWN_KINDS = ("pmc", "scav", "sniper")

_MARKER_TTL_SEC = 3600
_MARKER_CACHE_VER = "markers-v4"
_marker_cache: dict[str, dict[str, Any]] = {}


def _marker_cache_key(mode: str) -> str:
    return f"{mode}:{_MARKER_CACHE_VER}"

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
        "transit": "转图",
    }.get(key, raw or "—")


def _is_transit_extract(row: dict[str, Any]) -> bool:
    ident = str(row.get("id") or "")
    return ident.startswith("transit:") or str(row.get("faction") or "") == "转图"


def _extract_point_item(
    *,
    ident: str,
    name: str,
    faction: str,
    row: dict[str, Any],
    locale: dict[str, Any],
    seen: set[str],
) -> dict[str, Any] | None:
    loc = _locale_lookup(locale, name, ident) if name else ""
    label = loc or name or ident
    if not label or label in seen:
        return None
    seen.add(label)
    item: dict[str, Any] = {
        "id": ident,
        "name": label,
        "faction": _faction_label(faction),
    }
    _attach_point(item, row)
    _attach_outline(item, row)
    switches = _collect_switch_ids(row)
    if switches:
        item["switches"] = [{"id": sid, "name": ""} for sid in switches]
    transfer = _parse_transfer_item(row.get("transferItem") or row.get("transfer_item"))
    if transfer:
        name = _resolved_item_name(
            locale,
            transfer.get("name"),
            f"{transfer.get('id')} Name" if transfer.get("id") else "",
        )
        if name:
            transfer["name"] = name
        item["transfer_item"] = transfer
    return item


def _append_transits(
    out: list[dict[str, Any]],
    rows: list[Any],
    locale: dict[str, Any],
    seen: set[str],
) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_id = str(row.get("id") or "").strip()
        desc = str(row.get("description") or row.get("name") or "").strip()
        ident = f"transit:{raw_id or desc}"
        item = _extract_point_item(
            ident=ident,
            name=desc,
            faction="transit",
            row=row,
            locale=locale,
            seen=seen,
        )
        if item:
            out.append(item)


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
        item = _extract_point_item(
            ident=ident,
            name=name,
            faction=str(row.get("faction") or ""),
            row=row,
            locale=locale,
            seen=seen,
        )
        if item:
            out.append(item)
    transits = raw.get("transits") if isinstance(raw.get("transits"), list) else []
    _append_transits(out, transits, locale, seen)
    out.sort(key=lambda r: (r.get("faction") or "", r.get("name") or ""))
    return out


def _map_bosses(
    raw: dict[str, Any],
    mobs: dict[str, dict[str, Any]],
    locale: dict[str, Any],
    slugs: dict[str, str] | None = None,
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
        slug = ""
        if slugs:
            slug = str(slugs.get(mob_id) or "").strip()
        if not slug:
            slug = str((mob or {}).get("normalizedName") or "").strip()
        chance = float(spawn.get("spawnChance") or 0)
        out.append(
            {
                "id": mob_id,
                "slug": slug,
                "name": _mob_name(mob_id, mob or {}, locale),
                "kind": classify_boss_kind(mob_id, slug),
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


def classify_map_spawn(spawn: dict[str, Any]) -> str | None:
    """把 maps dump 的 spawn 归到 pmc / scav / sniper；boss 仍走 bosses.locations。"""
    categories = {
        str(item).strip().lower()
        for item in (spawn.get("categories") or [])
        if item is not None and str(item).strip()
    }
    sides = {
        str(item).strip().lower()
        for item in (spawn.get("sides") or [])
        if item is not None and str(item).strip()
    }
    if "boss" in categories:
        return None
    if "player" in categories and ("pmc" in sides or "all" in sides):
        return "pmc"
    if "sniper" in categories:
        return "sniper"
    if "scav" in sides and ("bot" in categories or "all" in categories):
        return "scav"
    return None


def _parse_map_spawns(rows: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spawn in rows or []:
        if not isinstance(spawn, dict):
            continue
        kind = classify_map_spawn(spawn)
        if kind not in SPAWN_KINDS:
            continue
        point = map_xyz(spawn.get("position") if "position" in spawn else spawn)
        if not point:
            continue
        out.append(
            {
                "kind": kind,
                "zone_name": str(spawn.get("zoneName") or spawn.get("zone_name") or ""),
                "x": point["x"],
                "y": point["y"],
                "z": point["z"],
            }
        )
    out.sort(key=lambda r: (str(r.get("kind") or ""), float(r.get("z") or 0), float(r.get("x") or 0)))
    return out


def _opt_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _opt_bottom(raw: dict[str, Any]) -> float | None:
    """炮区 dump 把 bottom 拼成 botom。"""
    value = _opt_float(raw.get("bottom"))
    if value is not None:
        return value
    return _opt_float(raw.get("botom"))


def _parse_outline(raw: Any) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        point = map_xyz(item) if isinstance(item, dict) else None
        if point:
            out.append(point)
    return out


def _has_xz(row: dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    return row.get("x") is not None and row.get("z") is not None


def _is_hex_item_id(raw: str) -> bool:
    key = (raw or "").strip()
    return len(key) >= 20 and all(ch in "0123456789abcdef" for ch in key.lower())


def _is_blank_item_label(raw: str) -> bool:
    key = (raw or "").strip()
    if not key or _is_hex_item_id(key):
        return True
    for suffix in (" Name", " ShortName", " Description"):
        if key.endswith(suffix):
            return _is_hex_item_id(key[: -len(suffix)].strip())
    return False


def _is_locale_key(raw: str) -> bool:
    text = (raw or "").strip()
    if not text:
        return False
    if "/" in text:
        return True
    return text.endswith((" Name", " ShortName", " Description"))


def _needs_display_name(raw: str) -> bool:
    return _is_blank_item_label(raw) or _is_locale_key(raw)


def _resolved_item_name(locale: dict[str, Any], *candidates: str) -> str:
    for raw in candidates:
        text = str(raw or "").strip()
        if not text:
            continue
        loc = _locale_lookup(locale, text) if locale else ""
        if loc and not _needs_display_name(loc):
            return loc
        if _needs_display_name(text):
            continue
        return text
    return ""


def _layer_needs_fill(rows: list[Any] | None) -> bool:
    if not isinstance(rows, list) or not rows:
        return True
    return any(isinstance(row, dict) and not _has_xz(row) for row in rows)


def _containers_need_names(rows: list[Any] | None) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("normalized_name") or "").strip()
        name = str(row.get("name") or "").strip()
        if not kind or _is_blank_item_label(kind) or _needs_display_name(name):
            return True
    return False


def _locks_need_key_names(rows: list[Any] | None) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return any(
        isinstance(row, dict)
        and str(row.get("key_id") or "").strip()
        and _is_blank_item_label(str(row.get("key_name") or ""))
        for row in rows
    )


def enrich_lock_keys(
    locks: list[Any],
    items_by_id: dict[str, dict[str, Any]],
) -> None:
    """用物品目录补门锁钥匙中文名 / 图标。"""
    for row in locks:
        if not isinstance(row, dict):
            continue
        key_id = str(row.get("key_id") or "").strip()
        if not key_id:
            continue
        item = items_by_id.get(key_id)
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        short_name = str(item.get("short_name") or "").strip()
        icon = str(item.get("icon_link") or "").strip()
        if name:
            row["key_name"] = name
        if short_name:
            row["key_short_name"] = short_name
        if icon:
            row["key_icon"] = icon


def _enrich_map_lock_keys(db: Session, locks: list[Any]) -> None:
    ids = {
        str(row.get("key_id") or "").strip()
        for row in locks
        if isinstance(row, dict)
    }
    ids.discard("")
    if not ids:
        return
    try:
        from app.services.tarkov.catalog import peek_catalog_items

        rows = peek_catalog_items(db)
    except Exception:  # noqa: BLE001
        logger.warning("map lock keys: items catalog unavailable", exc_info=True)
        return
    by_id = {
        str(item.get("id") or "").strip(): item
        for item in rows
        if isinstance(item, dict) and item.get("id")
    }
    enrich_lock_keys(locks, by_id)


def _copy_point(dst: dict[str, Any], src: dict[str, Any] | None) -> bool:
    if not isinstance(src, dict):
        return False
    changed = False
    if _has_xz(src):
        dst["x"] = src["x"]
        dst["y"] = src.get("y") if src.get("y") is not None else 0
        dst["z"] = src["z"]
        changed = True
    elif _fill_point_from_src(dst, src):
        changed = True
    if dst.get("top") is None:
        top = _opt_float(src.get("top"))
        if top is not None:
            dst["top"] = top
            changed = True
    if dst.get("bottom") is None:
        bottom = _opt_bottom(src)
        if bottom is not None:
            dst["bottom"] = bottom
            changed = True
    if not dst.get("outline"):
        outline = _parse_outline(src.get("outline"))
        if outline:
            dst["outline"] = outline
            changed = True
    return changed


def _attach_point(item: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    point = map_xyz(raw)
    if point:
        item["x"] = point["x"]
        item["y"] = point["y"]
        item["z"] = point["z"]
    top = _opt_float(raw.get("top"))
    bottom = _opt_bottom(raw)
    if top is not None:
        item["top"] = top
    if bottom is not None:
        item["bottom"] = bottom
    return item


def _attach_outline(item: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    outline = _parse_outline(raw.get("outline"))
    if outline:
        item["outline"] = outline
    return item


def _collect_switch_ids(row: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def add(raw: Any) -> None:
        ident = ""
        if isinstance(raw, str):
            ident = raw.strip()
        elif isinstance(raw, dict):
            ident = str(raw.get("id") or "").strip()
        if ident and ident not in seen:
            seen.add(ident)
            ids.append(ident)

    for item in row.get("switches") or []:
        add(item)
    add(row.get("switch"))
    return ids


def _parse_transfer_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    ref = _item_ref(raw.get("item"))
    ident = str(ref.get("id") or "").strip()
    if not ident:
        return None
    count = _as_int(raw.get("count"), 1) or 1
    ref["count"] = count
    return ref


def _item_ref(raw: Any) -> dict[str, str]:
    if isinstance(raw, str):
        ident = raw.strip()
        return {"id": ident, "name": "", "short_name": "", "icon_link": ""} if ident else {}
    if not isinstance(raw, dict):
        return {}
    ident = str(raw.get("id") or raw.get("_id") or "").strip()
    if not ident:
        return {}
    return {
        "id": ident,
        "name": str(raw.get("name") or ""),
        "short_name": str(raw.get("shortName") or raw.get("short_name") or ""),
        "icon_link": str(raw.get("iconLink") or raw.get("icon_link") or ""),
    }


def _localized(locale: dict[str, Any], *candidates: str) -> str:
    for raw in candidates:
        text = str(raw or "").strip()
        if not text:
            continue
        loc = _locale_lookup(locale, text) if locale else ""
        if loc:
            return loc
        return text
    return ""


_HAZARD_TYPE_LABELS = {
    "minefield": "雷区",
    "sniper": "狙击",
    "mortar": "迫击炮",
}


def _hazard_label(
    *,
    hazard_type: str,
    name: str,
    locale: dict[str, Any],
) -> str:
    loc = _localized(locale, name)
    if loc:
        return loc
    return _HAZARD_TYPE_LABELS.get(hazard_type, name or hazard_type or "危险区")


def _marker_id(prefix: str, *parts: Any) -> str:
    bits = [str(part).strip() for part in parts if part is not None and str(part).strip()]
    return f"{prefix}:{':'.join(bits)}" if bits else prefix


def _parse_map_locks(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        key = _item_ref(row.get("key"))
        lock_type = str(row.get("lockType") or row.get("lock_type") or "").strip()
        ident = str(row.get("id") or "").strip() or _marker_id(
            "lock",
            key.get("id"),
            lock_type,
            index,
        )
        key_id = key.get("id") or ""
        key_name = _resolved_item_name(
            lang,
            key.get("name"),
            f"{key_id} Name" if key_id else "",
        )
        item = _attach_point(
            {
                "id": ident,
                "lock_type": lock_type,
                "needs_power": bool(row.get("needsPower") or row.get("needs_power")),
                "key_id": key_id,
                "key_name": key_name,
                "key_short_name": key.get("short_name") or "",
                "key_icon": key.get("icon_link") or "",
            },
            row,
        )
        out.append(item)
    return out


def _parse_map_hazards(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
    *,
    default_type: str = "",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        hazard_type = str(
            row.get("hazardType") or row.get("hazard_type") or default_type or ""
        ).strip()
        name = _hazard_label(
            hazard_type=hazard_type,
            name=str(row.get("name") or ""),
            locale=lang,
        )
        ident = str(row.get("id") or "").strip() or _marker_id(
            "hazard",
            hazard_type,
            name,
            index,
        )
        out.append(
            _attach_outline(
                _attach_point(
                    {
                        "id": ident,
                        "hazard_type": hazard_type or default_type,
                        "name": name,
                    },
                    row,
                ),
                row,
            )
        )
    return out


def _parse_artillery_zones(
    artillery: Any,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if isinstance(artillery, dict):
        zones = artillery.get("zones")
    elif isinstance(artillery, list):
        zones = artillery
    else:
        zones = None
    return _parse_map_hazards(zones, locale, default_type="mortar")


def _parse_map_hazards_with_artillery(
    raw: dict[str, Any],
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    hazards = _parse_map_hazards(raw.get("hazards"), locale)
    seen = {
        (row.get("hazard_type"), row.get("x"), row.get("z"))
        for row in hazards
        if _has_xz(row)
    }
    for row in _parse_artillery_zones(raw.get("artillery"), locale):
        key = (row.get("hazard_type"), row.get("x"), row.get("z"))
        if _has_xz(row) and key in seen:
            continue
        hazards.append(row)
        if _has_xz(row):
            seen.add(key)
    return hazards


def _switch_target(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    name = str(raw.get("name") or raw.get("id") or "").strip()
    typename = str(raw.get("__typename") or raw.get("typename") or "").strip()
    if raw.get("faction") is not None or typename.endswith("Extract"):
        kind = "extract"
    else:
        kind = "switch"
    return {"name": name, "kind": kind}


def _parse_switch_activate(
    op: dict[str, Any],
    locale: dict[str, Any],
) -> dict[str, str] | None:
    """dump 是 extract/switch id；旧 GraphQL extras 才带 target 对象。"""
    operation = str(op.get("operation") or "").strip()
    extract_id = str(op.get("extract") or "").strip()
    switch_id = str(op.get("switch") or "").strip()
    target_raw = op.get("target")
    target_id = extract_id or switch_id
    kind = "extract" if extract_id else "switch" if switch_id else ""
    name = ""
    if isinstance(target_raw, dict):
        parsed = _switch_target(target_raw)
        name = _localized(locale, parsed.get("name"), op.get("name"))
        kind = parsed.get("kind") or kind or "switch"
        if not target_id:
            target_id = str(target_raw.get("id") or "").strip()
    elif not target_id:
        parsed = _switch_target(op)
        name = _localized(locale, parsed.get("name"), op.get("name"))
        kind = parsed.get("kind") or "switch"
    if not target_id and not name:
        return None
    out = {
        "operation": operation,
        "name": name,
        "kind": kind or "switch",
    }
    if target_id:
        out["target_id"] = target_id
    return out


def _parse_map_switches(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        ident = str(row.get("id") or "").strip() or _marker_id(
            "switch",
            row.get("name"),
            index,
        )
        activated = row.get("activatedBy")
        if activated is None:
            activated = row.get("activated_by")
        activated_by = ""
        if isinstance(activated, dict):
            activated_by = _localized(
                lang,
                activated.get("name"),
                activated.get("id"),
            )
        elif isinstance(activated, str):
            activated_by = activated.strip()
        activates: list[dict[str, str]] = []
        for op in row.get("activates") or []:
            if not isinstance(op, dict):
                continue
            parsed = _parse_switch_activate(op, lang)
            if parsed:
                activates.append(parsed)
        out.append(
            _attach_point(
                {
                    "id": ident,
                    "name": _localized(lang, row.get("name"), ident),
                    "switch_type": str(
                        row.get("switchType") or row.get("switch_type") or ""
                    ).strip(),
                    "activated_by": activated_by,
                    "activates": activates,
                },
                row,
            )
        )
    return out


def _parse_map_stationary_weapons(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    weapons = catalog or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        weapon = _resolve_catalog_ref(
            row.get("stationaryWeapon") or row.get("stationary_weapon"),
            weapons,
        )
        weapon_id = str(weapon.get("id") or row.get("id") or "").strip()
        name = _resolved_item_name(
            lang,
            weapon.get("name"),
            f"{weapon_id} Name" if weapon_id else "",
            weapon.get("shortName") or weapon.get("short_name"),
            f"{weapon_id} ShortName" if weapon_id else "",
            row.get("name"),
        ) or "固定武器"
        ident = weapon_id or _marker_id("stationary", name, index)
        out.append(_attach_point({"id": ident, "name": name}, row))
    return out


def _parse_map_btr_stops(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        name = _resolved_item_name(lang, row.get("name")) or "BTR"
        ident = str(row.get("id") or "").strip() or _marker_id("btr", name, index)
        item = {"id": ident, "name": name}
        point = map_xyz(row)
        if point:
            item["x"] = point["x"]
            item["y"] = point["y"]
            item["z"] = point["z"]
        out.append(item)
    return out


def _payload_id_catalog(payload: dict[str, Any], *keys: str) -> dict[str, dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return {}
    blob = None
    for key in keys:
        blob = data.get(key)
        if blob is not None:
            break
    out: dict[str, dict[str, Any]] = {}
    if isinstance(blob, dict):
        rows = blob.values()
    elif isinstance(blob, list):
        rows = blob
    else:
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ident = str(row.get("id") or row.get("_id") or "").strip()
        if ident:
            out[ident] = row
    return out


def _loot_containers_blob(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _payload_id_catalog(payload, "lootContainers", "loot_containers")


def _stationary_weapons_blob(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _payload_id_catalog(payload, "stationaryWeapons", "stationary_weapons")


def _resolve_catalog_ref(
    raw: Any,
    catalog: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    ident = ""
    extra: dict[str, Any] = {}
    if isinstance(raw, str):
        ident = raw.strip()
    elif isinstance(raw, dict):
        extra = raw
        ident = str(raw.get("id") or raw.get("_id") or "").strip()
    hit = catalog.get(ident) if catalog and ident else None
    if isinstance(hit, dict):
        merged = {**hit, **{key: value for key, value in extra.items() if value not in (None, "")}}
        if ident and not merged.get("id"):
            merged["id"] = ident
        return merged
    if extra:
        return extra
    return {"id": ident} if ident else {}


def _parse_map_loot_containers(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    boxes = catalog or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        box = _resolve_catalog_ref(
            row.get("lootContainer") or row.get("loot_container") or row.get("id"),
            boxes,
        )
        container_id = str(box.get("id") or "").strip()
        normalized = str(
            box.get("normalizedName") or box.get("normalized_name") or ""
        ).strip()
        if _is_blank_item_label(normalized):
            normalized = ""
        name = _resolved_item_name(
            lang,
            box.get("name"),
            f"{container_id} Name" if container_id else "",
            normalized,
        )
        ident = str(row.get("id") or "").strip() or _marker_id(
            "container",
            container_id or normalized,
            index,
        )
        out.append(
            _attach_point(
                {
                    "id": ident,
                    "container_id": container_id,
                    "name": name or normalized or "容器",
                    "normalized_name": normalized,
                },
                row,
            )
        )
    return out


def _parse_loot_item_ids(raw: Any) -> list[str]:
    if isinstance(raw, str):
        ident = raw.strip()
        return [ident] if ident else []
    if isinstance(raw, dict):
        ident = str(raw.get("id") or raw.get("_id") or "").strip()
        return [ident] if ident else []
    return []


def _parse_map_loot_loose(
    rows: list[Any] | None,
    locale: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lang = locale or {}
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in row.get("items") or []:
            for ident in _parse_loot_item_ids(entry):
                if ident in seen:
                    continue
                seen.add(ident)
                name = _resolved_item_name(lang, f"{ident} Name")
                items.append(
                    {
                        "id": ident,
                        "name": "" if _needs_display_name(name) else name,
                        "short_name": "",
                        "icon_link": "",
                        "types": [],
                        "handbook_ids": [],
                    }
                )
        if not items:
            continue
        ident = str(row.get("id") or "").strip() or _marker_id("loose", index)
        out.append(_attach_point({"id": ident, "items": items}, row))
    return out


def _link_extracts_and_switches(
    extracts: list[Any],
    switches: list[Any],
) -> None:
    switch_name = {
        str(row.get("id") or ""): str(row.get("name") or "")
        for row in switches
        if isinstance(row, dict) and row.get("id")
    }
    extract_name = {
        str(row.get("id") or ""): str(row.get("name") or "")
        for row in extracts
        if isinstance(row, dict) and row.get("id")
    }
    for sw in switches:
        if not isinstance(sw, dict):
            continue
        ab = str(sw.get("activated_by") or "").strip()
        if ab and ab in switch_name:
            sw["activated_by"] = switch_name[ab] or ab
        for act in sw.get("activates") or []:
            if not isinstance(act, dict):
                continue
            tid = str(act.get("target_id") or "").strip()
            if tid in extract_name:
                act["kind"] = "extract"
                act["name"] = extract_name[tid] or tid
            elif tid in switch_name:
                act["kind"] = "switch"
                act["name"] = switch_name[tid] or tid
            elif not str(act.get("name") or "").strip():
                act["name"] = tid
            act.pop("target_id", None)
    for ex in extracts:
        if not isinstance(ex, dict):
            continue
        linked: list[dict[str, str]] = []
        for item in ex.get("switches") or []:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id") or "").strip()
            if not sid:
                continue
            linked.append(
                {
                    "id": sid,
                    "name": switch_name.get(sid) or str(item.get("name") or "") or sid,
                }
            )
        if linked:
            ex["switches"] = linked


def _fill_item_refs(
    refs: list[Any],
    catalog: dict[str, dict[str, Any]],
) -> None:
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        ident = str(ref.get("id") or "").strip()
        item = catalog.get(ident) if ident else None
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name and _needs_display_name(str(ref.get("name") or "")):
            ref["name"] = name
        short = str(item.get("short_name") or "").strip()
        if short and not str(ref.get("short_name") or "").strip():
            ref["short_name"] = short
        icon = str(item.get("icon_link") or "").strip()
        if icon and not str(ref.get("icon_link") or "").strip():
            ref["icon_link"] = icon
        types = item.get("types")
        if isinstance(types, list) and not ref.get("types"):
            ref["types"] = [str(t) for t in types if t is not None and str(t).strip()]
        handbook = item.get("handbook_ids")
        if isinstance(handbook, list) and not ref.get("handbook_ids"):
            ref["handbook_ids"] = [
                str(cid).strip()
                for cid in handbook
                if cid is not None and str(cid).strip()
            ]


def _collect_map_item_refs(row: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for extract in row.get("extracts") or []:
        if not isinstance(extract, dict):
            continue
        transfer = extract.get("transfer_item")
        if isinstance(transfer, dict):
            refs.append(transfer)
    for loose in row.get("loot_loose") or []:
        if not isinstance(loose, dict):
            continue
        for item in loose.get("items") or []:
            if isinstance(item, dict):
                refs.append(item)
    return refs


def _enrich_map_item_refs(db: Session, row: dict[str, Any]) -> None:
    refs = _collect_map_item_refs(row)
    if not refs:
        return
    try:
        from app.services.tarkov.catalog import peek_catalog_items

        catalog_rows = peek_catalog_items(db)
    except Exception:
        logger.warning("map item refs: items catalog unavailable", exc_info=True)
        return
    by_id = {
        str(item.get("id") or "").strip(): item
        for item in catalog_rows
        if isinstance(item, dict) and item.get("id")
    }
    _fill_item_refs(refs, by_id)


def _row_needs_marker_meta(row: dict[str, Any]) -> bool:
    if "key_id" in row or "key_name" in row:
        return _is_blank_item_label(str(row.get("key_name") or "")) or not str(
            row.get("key_icon") or ""
        ).strip()
    kind = str(row.get("normalized_name") or "").strip()
    name = str(row.get("name") or "").strip()
    return (not kind or _is_blank_item_label(kind)) or _needs_display_name(name)


def _copy_marker_meta(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for key in (
        "name",
        "key_name",
        "key_short_name",
        "key_icon",
        "activated_by",
        "normalized_name",
        "container_id",
    ):
        current = str(dst.get(key) or "")
        incoming = src.get(key)
        if incoming and _needs_display_name(current):
            dst[key] = incoming


def _merge_marker_layer(
    existing: list[Any],
    incoming: list[dict[str, Any]],
    id_keys: tuple[str, ...],
    *,
    fill_meta: bool = False,
) -> list[dict[str, Any]]:
    current = [row for row in existing if isinstance(row, dict)]
    if not incoming:
        return current
    if not current:
        return incoming
    used: set[int] = set()

    def match_key(row: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(row.get(key) or "") for key in id_keys)

    for row in current:
        needs_point = not _has_xz(row)
        needs_meta = fill_meta and _row_needs_marker_meta(row)
        if not needs_point and not needs_meta:
            continue
        want = match_key(row)
        src = None
        if any(want):
            for index, item in enumerate(incoming):
                if index in used:
                    continue
                if match_key(item) == want:
                    src = item
                    used.add(index)
                    break
        if src is None:
            for index, item in enumerate(incoming):
                if index in used or not _has_xz(item):
                    continue
                src = item
                used.add(index)
                break
        if src:
            _copy_point(row, src)
            _copy_marker_meta(row, src)
    if not any(_has_xz(row) for row in current) and any(_has_xz(row) for row in incoming):
        return incoming
    return current


def _extracts_have_coords(extracts: list[dict[str, Any]]) -> bool:
    return any(
        row.get("x") is not None and row.get("z") is not None
        for row in extracts
        if isinstance(row, dict) and not _is_transit_extract(row)
    )


def _transit_raw_id(ident: str) -> str:
    key = str(ident or "").strip()
    if key.startswith("transit:"):
        return key[len("transit:") :].strip()
    return key


def _transits_missing(extracts: list[dict[str, Any]]) -> bool:
    return not any(
        _is_transit_extract(row) for row in extracts if isinstance(row, dict)
    )


def _transit_coords_missing(extracts: list[dict[str, Any]]) -> bool:
    return any(
        _is_transit_extract(row)
        and (row.get("x") is None or row.get("z") is None)
        for row in extracts
        if isinstance(row, dict)
    )


def _bosses_need_coords(bosses: list[Any]) -> bool:
    if not bosses:
        return False
    for boss in bosses:
        if not isinstance(boss, dict):
            continue
        locs = boss.get("locations") if isinstance(boss.get("locations"), list) else []
        if not locs:
            return True
        if not any(
            isinstance(loc, dict) and loc.get("positions") for loc in locs
        ):
            return True
    return False


def _cached_map_markers() -> dict[str, dict[str, Any]]:
    now = time.time()
    key = _marker_cache_key(parse_game_mode())
    entry = _marker_cache.get(key) or {}
    cached = entry.get("by_slug")
    if (
        isinstance(cached, dict)
        and cached
        and now - float(entry.get("at") or 0) < _MARKER_TTL_SEC
    ):
        return cached
    return {}


def _markers_from_maps_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    maps = _maps_blob(payload)
    if isinstance(maps, dict):
        rows = maps.values()
    elif isinstance(maps, list):
        rows = maps
    else:
        return {}
    by_slug: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        slug = resolve_map_slug(str(raw.get("normalizedName") or raw.get("nameId") or ""))
        if slug:
            by_slug[slug] = raw
    return by_slug


def _fill_point_from_src(extract: dict[str, Any], src: dict[str, Any] | None) -> bool:
    if not src:
        return False
    point = map_xyz(src)
    if not point:
        return False
    extract["x"] = point["x"]
    extract["y"] = point["y"]
    extract["z"] = point["z"]
    if extract.get("top") is None:
        top = _opt_float(src.get("top"))
        if top is not None:
            extract["top"] = top
    if extract.get("bottom") is None:
        bottom = _opt_bottom(src)
        if bottom is not None:
            extract["bottom"] = bottom
    if not extract.get("outline"):
        outline = _parse_outline(src.get("outline"))
        if outline:
            extract["outline"] = outline
    if not extract.get("switches"):
        ids = _collect_switch_ids(src)
        if ids:
            extract["switches"] = [{"id": sid, "name": ""} for sid in ids]
    if not extract.get("transfer_item"):
        transfer = _parse_transfer_item(src.get("transferItem") or src.get("transfer_item"))
        if transfer:
            extract["transfer_item"] = transfer
    return True


def _apply_map_markers(
    row: dict[str, Any],
    locale: dict[str, Any] | None = None,
    *,
    overlay: dict[str, dict[str, Any]] | None = None,
) -> None:
    extracts = row.get("extracts") if isinstance(row.get("extracts"), list) else []
    bosses = row.get("bosses") if isinstance(row.get("bosses"), list) else []
    need_coords = not _extracts_have_coords(extracts)
    need_transits = _transits_missing(extracts)
    need_transit_coords = _transit_coords_missing(extracts)
    need_boss_coords = _bosses_need_coords(bosses)
    need_spawns = not (
        isinstance(row.get("spawns"), list) and len(row.get("spawns") or []) > 0
    )
    need_locks = _layer_needs_fill(
        row.get("locks") if isinstance(row.get("locks"), list) else []
    ) or _locks_need_key_names(
        row.get("locks") if isinstance(row.get("locks"), list) else []
    )
    need_hazards = _layer_needs_fill(
        row.get("hazards") if isinstance(row.get("hazards"), list) else []
    )
    need_switches = _layer_needs_fill(
        row.get("switches") if isinstance(row.get("switches"), list) else []
    )
    need_stationary = _layer_needs_fill(
        row.get("stationary_weapons")
        if isinstance(row.get("stationary_weapons"), list)
        else []
    )
    need_btr = _layer_needs_fill(
        row.get("btr_stops") if isinstance(row.get("btr_stops"), list) else []
    )
    need_containers = _layer_needs_fill(
        row.get("loot_containers")
        if isinstance(row.get("loot_containers"), list)
        else []
    ) or _containers_need_names(
        row.get("loot_containers")
        if isinstance(row.get("loot_containers"), list)
        else []
    )
    need_loot_loose = _layer_needs_fill(
        row.get("loot_loose") if isinstance(row.get("loot_loose"), list) else []
    )
    if (
        not need_coords
        and not need_transits
        and not need_transit_coords
        and not need_boss_coords
        and not need_spawns
        and not need_locks
        and not need_hazards
        and not need_switches
        and not need_stationary
        and not need_btr
        and not need_containers
        and not need_loot_loose
    ):
        return
    by_slug = overlay if overlay is not None else _cached_map_markers()
    extra = by_slug.get(str(row.get("slug") or "")) or by_slug.get(str(row.get("id") or ""))
    if not extra:
        return
    gql_extracts = extra.get("extracts") if isinstance(extra.get("extracts"), list) else []
    gql_transits = extra.get("transits") if isinstance(extra.get("transits"), list) else []
    extract_by_id = {
        str(item.get("id") or ""): item
        for item in gql_extracts
        if isinstance(item, dict) and item.get("id")
    }
    extract_by_name = {
        str(item.get("name") or ""): item
        for item in gql_extracts
        if isinstance(item, dict) and item.get("name")
    }
    transit_by_id = {
        str(item.get("id") or ""): item
        for item in gql_transits
        if isinstance(item, dict) and item.get("id") is not None
    }
    transit_by_desc = {
        str(item.get("description") or item.get("name") or ""): item
        for item in gql_transits
        if isinstance(item, dict)
        and (item.get("description") or item.get("name"))
    }
    for extract in extracts:
        if not isinstance(extract, dict):
            continue
        if extract.get("x") is not None and extract.get("z") is not None:
            continue
        if _is_transit_extract(extract):
            raw_id = _transit_raw_id(str(extract.get("id") or ""))
            src = transit_by_id.get(raw_id) or transit_by_desc.get(
                str(extract.get("name") or "")
            )
            # 兼容 locale 前原始 description 仍写在 id 后缀里的情况
            if not src and raw_id and raw_id not in transit_by_id:
                src = transit_by_desc.get(raw_id)
            _fill_point_from_src(extract, src if isinstance(src, dict) else None)
            continue
        src = extract_by_id.get(str(extract.get("id") or "")) or extract_by_name.get(
            str(extract.get("name") or "")
        )
        _fill_point_from_src(extract, src if isinstance(src, dict) else None)
    if need_transits:
        seen = {str(item.get("name") or "") for item in extracts if isinstance(item, dict)}
        _append_transits(extracts, gql_transits, locale or {}, seen)
        extracts.sort(key=lambda r: (str(r.get("faction") or ""), str(r.get("name") or "")))
    if need_boss_coords:
        gql_bosses = extra.get("bosses") if isinstance(extra.get("bosses"), list) else []
        gql_by_slug = {
            str(item.get("normalizedName") or ""): item
            for item in gql_bosses
            if isinstance(item, dict) and item.get("normalizedName")
        }
        for boss in bosses:
            if not isinstance(boss, dict):
                continue
            locs = boss.get("locations") if isinstance(boss.get("locations"), list) else []
            if any(loc.get("positions") for loc in locs if isinstance(loc, dict)):
                continue
            src = gql_by_slug.get(str(boss.get("slug") or ""))
            if not src:
                continue
            boss["locations"] = _boss_locations(src, locale or {})
    if need_spawns:
        gql_spawns = extra.get("spawns") if isinstance(extra.get("spawns"), list) else []
        row["spawns"] = _parse_map_spawns(gql_spawns)
    if need_locks:
        gql_locks = extra.get("locks") if isinstance(extra.get("locks"), list) else []
        row["locks"] = _merge_marker_layer(
            row.get("locks") if isinstance(row.get("locks"), list) else [],
            _parse_map_locks(gql_locks, locale or {}),
            ("key_id", "lock_type"),
            fill_meta=True,
        )
    if need_hazards:
        gql_hazards = extra.get("hazards") if isinstance(extra.get("hazards"), list) else []
        incoming = _parse_map_hazards(gql_hazards, locale or {})
        incoming.extend(_parse_artillery_zones(extra.get("artillery"), locale or {}))
        row["hazards"] = _merge_marker_layer(
            row.get("hazards") if isinstance(row.get("hazards"), list) else [],
            incoming,
            ("hazard_type", "name"),
        )
    if need_switches:
        gql_switches = extra.get("switches") if isinstance(extra.get("switches"), list) else []
        row["switches"] = _merge_marker_layer(
            row.get("switches") if isinstance(row.get("switches"), list) else [],
            _parse_map_switches(gql_switches, locale or {}),
            ("id", "name"),
        )
    if need_stationary:
        gql_stationary = (
            extra.get("stationaryWeapons")
            if isinstance(extra.get("stationaryWeapons"), list)
            else extra.get("stationary_weapons")
            if isinstance(extra.get("stationary_weapons"), list)
            else []
        )
        row["stationary_weapons"] = _merge_marker_layer(
            row.get("stationary_weapons")
            if isinstance(row.get("stationary_weapons"), list)
            else [],
            _parse_map_stationary_weapons(gql_stationary, locale or {}),
            ("id", "name"),
        )
    if need_btr:
        gql_btr = (
            extra.get("btrStops")
            if isinstance(extra.get("btrStops"), list)
            else extra.get("btr_stops")
            if isinstance(extra.get("btr_stops"), list)
            else []
        )
        row["btr_stops"] = _merge_marker_layer(
            row.get("btr_stops") if isinstance(row.get("btr_stops"), list) else [],
            _parse_map_btr_stops(gql_btr, locale or {}),
            ("name",),
        )
    if need_containers:
        gql_boxes = (
            extra.get("lootContainers")
            if isinstance(extra.get("lootContainers"), list)
            else extra.get("loot_containers")
            if isinstance(extra.get("loot_containers"), list)
            else []
        )
        row["loot_containers"] = _merge_marker_layer(
            row.get("loot_containers")
            if isinstance(row.get("loot_containers"), list)
            else [],
            _parse_map_loot_containers(gql_boxes, locale or {}),
            ("container_id", "normalized_name"),
            fill_meta=True,
        )
    if need_loot_loose:
        gql_loose = (
            extra.get("lootLoose")
            if isinstance(extra.get("lootLoose"), list)
            else extra.get("loot_loose")
            if isinstance(extra.get("loot_loose"), list)
            else []
        )
        row["loot_loose"] = _merge_marker_layer(
            row.get("loot_loose") if isinstance(row.get("loot_loose"), list) else [],
            _parse_map_loot_loose(gql_loose, locale or {}),
            ("id",),
        )
    _link_extracts_and_switches(
        row.get("extracts") if isinstance(row.get("extracts"), list) else [],
        row.get("switches") if isinstance(row.get("switches"), list) else [],
    )


def parse_map_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locale = payload.get("locale") if isinstance(payload.get("locale"), dict) else {}
    maps = _maps_blob(payload)
    mobs = _mobs_blob(payload)
    container_catalog = _loot_containers_blob(payload)
    weapon_catalog = _stationary_weapons_blob(payload)
    slugs = assign_boss_slugs(_spawn_mobs(maps, mobs))
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
                "bosses": _map_bosses(raw, mobs, locale, slugs),
                "spawns": _parse_map_spawns(raw.get("spawns")),
                "locks": _parse_map_locks(raw.get("locks"), locale),
                "hazards": _parse_map_hazards_with_artillery(raw, locale),
                "switches": _parse_map_switches(raw.get("switches"), locale),
                "stationary_weapons": _parse_map_stationary_weapons(
                    raw.get("stationaryWeapons") or raw.get("stationary_weapons"),
                    locale,
                    weapon_catalog,
                ),
                "btr_stops": _parse_map_btr_stops(
                    raw.get("btrStops") or raw.get("btr_stops"),
                    locale,
                ),
                "loot_containers": _parse_map_loot_containers(
                    raw.get("lootContainers") or raw.get("loot_containers"),
                    locale,
                    container_catalog,
                ),
                "loot_loose": _parse_map_loot_loose(
                    raw.get("lootLoose") or raw.get("loot_loose"),
                    locale,
                ),
            }
        )
        _link_extracts_and_switches(rows[-1]["extracts"], rows[-1]["switches"])
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
    if get_maps_raw(db) is None:
        ensure_maps(db)
    source, payload, synced_at, note = load_maps_payload(db)
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
    if get_maps_raw(db) is None:
        ensure_maps(db)
    source, payload, synced_at, note = load_maps_payload(db)
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
    _apply_map_markers(row, locale, overlay=_markers_from_maps_payload(payload))
    locks = row.get("locks") if isinstance(row.get("locks"), list) else []
    _enrich_map_lock_keys(db, locks)
    _enrich_map_item_refs(db, row)
    return {
        **row,
        "variants": variants,
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }
