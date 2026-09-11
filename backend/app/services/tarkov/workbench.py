"""枪械工作台：从 items dump 索引槽位 / 允许件 / 冲突，计算人机后坐。

不新建派生表；读 catalog 已加载的 json.tarkov.dev items raw。
精确度 / 膛口初速 / 手臂耐力的字段与合成式对齐 EFTForge 对同一 dump 的投影
（centerOfImpact、properties.accuracyModifier、顶栏 velocity、弹药 initialSpeed），
不为补字段打 GraphQL。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov import catalog as catalog_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov.items import TarkovItemsError
from app.services.tarkov.overlay import parsed_cache_key

logger = logging.getLogger(__name__)

_WEAPON_TYPES = {"ItemPropertiesWeapon"}
_PRESET_PROP_TYPES = {"ItemPropertiesPreset"}
_PRESET_TYPE = "preset"


class TarkovWorkbenchError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_prop_float(props: dict[str, Any] | None, key: str) -> float | None:
    if not props or key not in props or props.get(key) in (None, ""):
        return None
    return _as_float(props.get(key))


# dump 的 COI 为 100m 处米制散布；合成 MOA 用 34.36（与 EFTForge stats.py 同一常数）。
_COI_TO_MOA = 34.36
# 手臂耐力默认力量 10 级，与 EFTForge 前端/接口默认一致；/1.04 与 10×0.004 相消。
_ARM_STAMINA_STRENGTH = 10


def evo_ergo_delta(ergo: float, weight: float, equip_ergo: float = 0.0) -> float:
    """Evo 人机 Delta：-15 × (重量 − 人机重量上限)。正值未过摆。"""
    adjusted = ergo * (1 + equip_ergo)
    cap = 0.0007556 * (adjusted**2) + 0.02736 * adjusted + 2.9159
    return round(-15.0 * (weight - cap), 2)


def arm_stamina_seconds(
    weight: float,
    ergo: float,
    strength_level: int = _ARM_STAMINA_STRENGTH,
    equip_ergo: float = 0.0,
) -> float:
    """站立开镜手臂耐力耗尽秒数。"""
    safe_weight = weight if weight > 0 else 0.0
    bonus = 1 + equip_ergo / 2
    return round(
        ((85.5 / (safe_weight + 0.65)) + 9.15 + 0.06477 * ergo * bonus)
        / 1.04
        * (1 + strength_level * 0.004),
        1,
    )


def accuracy_moa(base_coi: float | None, accuracy_pct: float) -> float | None:
    """枪管 COI 覆盖枪身；其余配件精度修正按百分点求和后一次叠上。"""
    if base_coi is None or base_coi <= 0:
        return None
    return round(_COI_TO_MOA * base_coi * (1 - accuracy_pct / 100), 2)


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _id_of(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("id") or value.get("_id") or "").strip()
    return ""


def _contains_item_ids(raw: dict[str, Any], props: dict[str, Any]) -> list[str]:
    blobs: list[Any] = []
    if isinstance(raw.get("containsItems"), list):
        blobs.append(raw.get("containsItems"))
    if isinstance(props.get("containsItems"), list):
        blobs.append(props.get("containsItems"))
    out: list[str] = []
    for contains in blobs:
        if not isinstance(contains, list):
            continue
        for entry in contains:
            ident = _id_of(entry.get("item") if isinstance(entry, dict) else entry)
            if ident:
                out.append(ident)
    return out


def _id_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for key, val in value.items():
            ident = _id_of(val) or str(key).strip()
            if ident:
                out.append(ident)
        return out
    if not isinstance(value, list):
        ident = _id_of(value)
        return [ident] if ident else []
    out = []
    for entry in value:
        ident = _id_of(entry)
        if ident:
            out.append(ident)
    return out


def _slot_filters(slot: dict[str, Any]) -> dict[str, Any]:
    filters = slot.get("filters")
    if isinstance(filters, list) and filters:
        first = filters[0]
        return first if isinstance(first, dict) else {}
    return filters if isinstance(filters, dict) else {}


def _locale_text(locale: dict[str, Any], raw: Any, fallback: str = "") -> str:
    text = str(raw or "").strip()
    if not text:
        return fallback
    hit = locale.get(text)
    if isinstance(hit, str) and hit.strip():
        return hit.strip()
    if text.endswith(" Name") and " " in text:
        return fallback or text.rsplit(" ", 1)[0]
    return text


def _cheapest_trader_rub(raw: dict[str, Any]) -> int | None:
    buys = raw.get("buyFromTrader")
    if not isinstance(buys, list):
        return None
    best: int | None = None
    for row in buys:
        if not isinstance(row, dict):
            continue
        price = _as_int(row.get("priceRUB") or row.get("price"), None)
        if price is None or price <= 0:
            continue
        if best is None or price < best:
            best = price
    return best


def _item_price_rub(raw: dict[str, Any]) -> int | None:
    trader = _cheapest_trader_rub(raw)
    flea = _as_int(raw.get("lastLowPrice") or raw.get("avg24hPrice"), None)
    candidates = [n for n in (trader, flea) if n is not None and n > 0]
    return min(candidates) if candidates else None


@dataclass
class WbSlot:
    id: str
    name: str
    name_id: str
    required: bool
    parent_item_id: str
    allowed_ids: list[str] = field(default_factory=list)


def _source_names(item_id: str, raw: dict[str, Any]) -> tuple[str, str]:
    """dump 英文名（未 overlay 中文）。出图站检索要用这个，不能用中文名。"""
    name = str(raw.get("name") or "").strip()
    short = str(raw.get("shortName") or "").strip()
    if name == f"{item_id} Name":
        name = ""
    if short == f"{item_id} ShortName":
        short = ""
    return name, short


@dataclass
class WbItem:
    id: str
    name: str
    short_name: str
    name_en: str
    short_name_en: str
    icon_link: str
    image_link: str
    weight: float
    ergo: float
    recoil_mod: float
    recoil_v: int
    recoil_h: int
    sighting_range: int
    mag_capacity: int
    is_weapon: bool
    is_ammo: bool
    caliber: str
    types: list[str]
    categories: set[str]
    conflicting: set[str]
    slots: list[WbSlot]
    factory_ids: list[str]
    default_ammo_id: str
    allowed_ammo: list[str]
    price_rub: int | None
    preset_image_link: str = ""
    base_item_id: str = ""
    default_preset_id: str = ""
    center_of_impact: float | None = None
    velocity_mod: float = 0.0
    accuracy_mod: float = 0.0
    initial_speed: float = 0.0


@dataclass
class WorkbenchIndex:
    items: dict[str, WbItem]
    slots: dict[str, WbSlot]
    by_category: dict[str, list[str]]


_index_lock = threading.Lock()
_index_cache: tuple[str, WorkbenchIndex] | None = None


def _parse_slots(
    parent_id: str,
    props: dict[str, Any],
    locale: dict[str, Any],
    by_category: dict[str, list[str]],
    excluded_global: set[str],
) -> list[WbSlot]:
    raw_slots = props.get("slots")
    if not isinstance(raw_slots, list):
        return []
    out: list[WbSlot] = []
    for slot in raw_slots:
        if not isinstance(slot, dict):
            continue
        slot_id = _id_of(slot)
        if not slot_id:
            continue
        filters = _slot_filters(slot)
        allowed = _id_list(filters.get("allowedItems"))
        excluded = set(_id_list(filters.get("excludedItems"))) | excluded_global
        for cat in _id_list(filters.get("allowedCategories")):
            for item_id in by_category.get(cat, []):
                if item_id not in allowed:
                    allowed.append(item_id)
        allowed = [iid for iid in allowed if iid not in excluded]
        out.append(
            WbSlot(
                id=slot_id,
                name=_locale_text(
                    locale, slot.get("name"), str(slot.get("nameId") or slot_id)
                ),
                name_id=str(slot.get("nameId") or "").strip(),
                required=bool(slot.get("required")),
                parent_item_id=parent_id,
                allowed_ids=allowed,
            )
        )
    return out


def build_index(source: str, payload: dict[str, Any]) -> WorkbenchIndex:
    locale = items_svc._locale_map(payload)
    by_category: dict[str, list[str]] = {}
    raw_by_id: dict[str, dict[str, Any]] = {}
    for item_id, raw in catalog_svc.iter_raw_items(source, payload):
        if not item_id or not isinstance(raw, dict):
            continue
        raw_by_id[item_id] = raw
        cats = raw.get("categories")
        for cat in _id_list(cats):
            by_category.setdefault(cat, []).append(item_id)

    items: dict[str, WbItem] = {}
    slots: dict[str, WbSlot] = {}
    for item_id, raw in raw_by_id.items():
        props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
        ptype = str(props.get("propertiesType") or props.get("__typename") or "")
        types = [str(t) for t in (raw.get("types") or []) if t]
        type_set = {t.lower() for t in types}
        name, short_name, _desc = catalog_svc._localized_name(item_id, raw, locale)
        name_en, short_name_en = _source_names(item_id, raw)
        is_preset = ptype in _PRESET_PROP_TYPES or _PRESET_TYPE in type_set
        is_weapon = (not is_preset) and (ptype in _WEAPON_TYPES or "gun" in type_set)
        is_ammo = ptype == "ItemPropertiesAmmo" or "ammo" in type_set
        factory_ids = _contains_item_ids(raw, props) if is_preset else []
        preset_image = str(raw.get("image512pxLink") or "") if is_preset else ""
        base_item_id = _id_of(props.get("baseItem")) if is_preset else ""
        preset_id = _id_of(props.get("defaultPreset"))
        if preset_id and not is_preset:
            preset = raw_by_id.get(preset_id)
            if isinstance(preset, dict):
                preset_image = str(preset.get("image512pxLink") or "")
                preset_props = (
                    preset.get("properties")
                    if isinstance(preset.get("properties"), dict)
                    else {}
                )
                factory_ids = _contains_item_ids(preset, preset_props)
        conflicting = set(_id_list(raw.get("conflictingItems")))
        item_slots = _parse_slots(item_id, props, locale, by_category, set())
        ergo = _as_float(raw.get("ergonomicsModifier"))
        if ergo == 0:
            ergo = _as_float(props.get("ergonomics"))
        if is_weapon:
            ergo = _as_float(props.get("ergonomics"))
        accuracy_mod = 0.0
        if not is_weapon and not is_ammo:
            acc = props.get("accuracyModifier")
            if acc not in (None, ""):
                accuracy_mod = _as_float(acc)
        wb = WbItem(
            id=item_id,
            name=name,
            short_name=short_name,
            name_en=name_en,
            short_name_en=short_name_en,
            icon_link=str(raw.get("baseImageLink") or raw.get("iconLink") or ""),
            image_link=str(raw.get("image512pxLink") or ""),
            weight=_as_float(raw.get("weight")),
            ergo=ergo,
            recoil_mod=_as_float(props.get("recoilModifier")),
            recoil_v=int(_as_float(props.get("recoilVertical"))),
            recoil_h=int(_as_float(props.get("recoilHorizontal"))),
            sighting_range=int(_as_float(props.get("sightingRange"))),
            mag_capacity=int(_as_float(props.get("capacity"))),
            is_weapon=is_weapon,
            is_ammo=is_ammo,
            caliber=str(props.get("caliber") or ""),
            types=types,
            categories=set(_id_list(raw.get("categories"))),
            conflicting=conflicting,
            slots=item_slots,
            factory_ids=factory_ids,
            default_ammo_id=_id_of(props.get("defaultAmmo")),
            allowed_ammo=_id_list(props.get("allowedAmmo")),
            price_rub=_item_price_rub(raw),
            preset_image_link=preset_image,
            base_item_id=base_item_id,
            default_preset_id=preset_id if not is_preset else "",
            center_of_impact=_optional_prop_float(props, "centerOfImpact"),
            velocity_mod=_as_float(raw.get("velocity")),
            accuracy_mod=accuracy_mod,
            initial_speed=_optional_prop_float(props, "initialSpeed") or 0.0,
        )
        items[item_id] = wb
        for slot in item_slots:
            slots[slot.id] = slot
    return WorkbenchIndex(items=items, slots=slots, by_category=by_category)


def load_index(db: Session) -> WorkbenchIndex:
    global _index_cache
    items_svc.ensure_items(db)
    try:
        catalog_svc.ensure_full_item_catalog(db)
    except TarkovItemsError as exc:
        raise TarkovWorkbenchError(str(exc)) from exc
    _source, synced, _note = items_svc.items_raw_header(db)
    key = parsed_cache_key(db, synced)
    with _index_lock:
        cached = _index_cache
        if cached is not None and cached[0] == key:
            return cached[1]
    try:
        source, payload, synced_at, _note = catalog_svc._load_payload(db)
    except TarkovItemsError as exc:
        raise TarkovWorkbenchError(str(exc)) from exc
    index = build_index(source, payload)
    key = parsed_cache_key(db, synced_at)
    with _index_lock:
        _index_cache = (key, index)
    return index


def item_summary(item: WbItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "short_name": item.short_name,
        "icon_link": item.icon_link,
        "ergonomics": item.ergo,
        "recoil_modifier": item.recoil_mod,
        "weight": item.weight,
        "price_rub": item.price_rub,
        "sighting_range": item.sighting_range or None,
        "mag_capacity": item.mag_capacity or None,
        "conflicting_ids": sorted(item.conflicting),
        "category_ids": sorted(item.categories),
    }


def slot_out(slot: WbSlot) -> dict[str, Any]:
    return {
        "id": slot.id,
        "name": slot.name,
        "name_id": slot.name_id,
        "required": slot.required,
        "parent_item_id": slot.parent_item_id,
    }


def _factory_ids_for(index: WorkbenchIndex, gun_id: str, weapon: WbItem) -> list[str]:
    looked = index.items.get((gun_id or "").strip())
    if looked and not looked.is_weapon and looked.factory_ids:
        return list(looked.factory_ids)
    return list(weapon.factory_ids)


def map_factory_pairs(index: WorkbenchIndex, gun_id: str) -> list[tuple[str, str]]:
    try:
        gun = _require_gun(index, gun_id)
    except TarkovWorkbenchError:
        return []
    remaining = _factory_ids_for(index, gun_id, gun)
    pairs: list[tuple[str, str]] = []

    def fill(item_id: str) -> None:
        item = index.items.get(item_id)
        if not item:
            return
        for slot in item.slots:
            allowed = set(slot.allowed_ids)
            found = ""
            for fid in remaining:
                if fid in allowed:
                    found = fid
                    break
            if not found:
                continue
            remaining.remove(found)
            pairs.append((slot.id, found))
            fill(found)

    fill(gun.id)
    return pairs


def _pairs_map(pairs: list[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for slot_id, item_id in pairs:
        if slot_id and item_id:
            out[slot_id] = item_id
    return out


def build_slot_tree(
    index: WorkbenchIndex,
    item_id: str,
    installed: dict[str, str],
) -> list[dict[str, Any]]:
    item = index.items.get(item_id)
    if not item:
        return []
    tree: list[dict[str, Any]] = []
    for slot in item.slots:
        child_id = installed.get(slot.id, "")
        child = index.items.get(child_id) if child_id else None
        node = {
            **slot_out(slot),
            "installed": item_summary(child) if child else None,
            "children": build_slot_tree(index, child.id, installed) if child else [],
        }
        tree.append(node)
    return tree


def _collect_installed_ids(
    index: WorkbenchIndex, gun_id: str, installed: dict[str, str]
) -> list[str]:
    ids: list[str] = []

    def walk(item_id: str) -> None:
        item = index.items.get(item_id)
        if not item:
            return
        for slot in item.slots:
            child_id = installed.get(slot.id, "")
            if not child_id:
                continue
            ids.append(child_id)
            walk(child_id)

    walk(gun_id)
    return ids


def _conflict_ids(index: WorkbenchIndex, installed_ids: list[str]) -> list[str]:
    present = set(installed_ids)
    flagged: list[str] = []
    seen: set[str] = set()
    for item_id in installed_ids:
        item = index.items.get(item_id)
        if not item:
            continue
        hits = item.conflicting & present
        if not hits:
            continue
        if item_id not in seen:
            flagged.append(item_id)
            seen.add(item_id)
        for other in sorted(hits):
            if other not in seen:
                flagged.append(other)
                seen.add(other)
    return flagged


def calculate_stats(
    index: WorkbenchIndex,
    gun_id: str,
    pairs: list[tuple[str, str]],
    ammo_id: str | None = None,
) -> dict[str, Any]:
    gun = _require_gun(index, gun_id)
    installed = _pairs_map(pairs)
    mod_ids = _collect_installed_ids(index, gun.id, installed)
    ergo = gun.ergo
    weight = gun.weight
    recoil_mod = 0.0
    velocity_pct = gun.velocity_mod
    sighting = gun.sighting_range
    mag_capacity = 0
    price = gun.price_rub or 0
    priced = 1 if gun.price_rub else 0
    barrel_coi: float | None = None
    accuracy_pct = 0.0
    for mod_id in mod_ids:
        mod = index.items.get(mod_id)
        if not mod:
            continue
        ergo += mod.ergo
        weight += mod.weight
        recoil_mod += mod.recoil_mod
        velocity_pct += mod.velocity_mod
        if not mod.is_weapon and mod.center_of_impact is not None:
            barrel_coi = mod.center_of_impact
        else:
            accuracy_pct += mod.accuracy_mod * 100
        if mod.sighting_range > sighting:
            sighting = mod.sighting_range
        if mod.mag_capacity > mag_capacity:
            mag_capacity = mod.mag_capacity
        if mod.price_rub:
            price += mod.price_rub
            priced += 1
    recoil_v = round(gun.recoil_v * (1 + recoil_mod))
    recoil_h = round(gun.recoil_h * (1 + recoil_mod))
    ammo = index.items.get(ammo_id or "") if ammo_id else None
    if ammo and ammo.is_ammo and mag_capacity:
        weight += ammo.weight * mag_capacity
        if ammo.price_rub:
            price += ammo.price_rub * mag_capacity
            priced += 1
    eed_kg = 0.0007556 * (ergo**2) + 0.02736 * ergo + 2.9159
    evo_weight = weight - eed_kg
    muzzle_velocity = None
    if ammo and ammo.is_ammo and ammo.initial_speed > 0:
        muzzle_velocity = round(ammo.initial_speed * (1 + velocity_pct / 100))
    base_coi = barrel_coi if barrel_coi is not None else gun.center_of_impact
    return {
        "ergonomics": round(ergo, 2),
        "recoil_vertical": recoil_v,
        "recoil_horizontal": recoil_h,
        "weight": round(weight, 3),
        "sighting_range": sighting or None,
        "mag_capacity": mag_capacity or None,
        "price_rub": price if priced else None,
        "conflicts": _conflict_ids(index, mod_ids),
        "overswing": evo_weight > 0,
        "ammo_id": ammo.id if ammo and ammo.is_ammo else None,
        "accuracy_moa": accuracy_moa(base_coi, accuracy_pct),
        "muzzle_velocity": muzzle_velocity,
        "arm_stamina": arm_stamina_seconds(weight, ergo),
        "evo_ergo_delta": evo_ergo_delta(ergo, weight),
    }


def _require_gun(index: WorkbenchIndex, gun_id: str) -> WbItem:
    """枪支表用默认预设 id；工作台要落到机匣。"""
    ident = (gun_id or "").strip()
    item = index.items.get(ident)
    if item and item.is_weapon:
        return item
    if item and item.base_item_id:
        base = index.items.get(item.base_item_id)
        if base and base.is_weapon:
            return base
    for other in index.items.values():
        if other.is_weapon and other.default_preset_id == ident:
            return other
    raise TarkovWorkbenchError("未找到枪械", status_code=404)


def ammo_summaries(index: WorkbenchIndex, gun: WbItem) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ammo_id in gun.allowed_ammo:
        if ammo_id in seen:
            continue
        ammo = index.items.get(ammo_id)
        if not ammo:
            continue
        seen.add(ammo_id)
        out.append(item_summary(ammo))
    return out


def get_gun(db: Session, gun_id: str) -> dict[str, Any]:
    index = load_index(db)
    gun = _require_gun(index, gun_id)
    factory = map_factory_pairs(index, gun_id)
    installed = _pairs_map(factory)
    stats = calculate_stats(index, gun.id, factory, gun.default_ammo_id or None)
    source, synced_at, note = items_svc.items_raw_header(db)
    return {
        "id": gun.id,
        "name": gun.name,
        "short_name": gun.short_name,
        "icon_link": gun.icon_link,
        "image_link": gun.image_link,
        "preset_image_link": gun.preset_image_link,
        "caliber": gun.caliber,
        "slots": build_slot_tree(index, gun.id, installed),
        "factory_pairs": [
            {"slot_id": slot_id, "item_id": item_id} for slot_id, item_id in factory
        ],
        "ammo": ammo_summaries(index, gun),
        "default_ammo_id": gun.default_ammo_id,
        "stats": stats,
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def allowed_items_for_slots(db: Session, slot_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    index = load_index(db)
    out: dict[str, list[dict[str, Any]]] = {}
    for slot_id in slot_ids:
        slot = index.slots.get(str(slot_id or "").strip())
        if not slot:
            out[str(slot_id or "")] = []
            continue
        items: list[dict[str, Any]] = []
        for item_id in slot.allowed_ids:
            item = index.items.get(item_id)
            if item:
                items.append(item_summary(item))
        out[slot.id] = items
    return out


_MAX_COMPAT_PAIRS = 200


def compatible_pairs(
    index: WorkbenchIndex,
    gun: WbItem,
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """丢掉本站 dump 不认识、或不从枪槽树可达的槽/件。"""
    installed: dict[str, str] = {}
    for slot_id, item_id in _pairs_map(pairs).items():
        slot = index.slots.get(slot_id)
        if slot is None or item_id not in slot.allowed_ids:
            continue
        installed[slot_id] = item_id
    out: list[tuple[str, str]] = []

    def walk(item_id: str) -> None:
        if len(out) >= _MAX_COMPAT_PAIRS:
            return
        item = index.items.get(item_id)
        if not item:
            return
        for slot in item.slots:
            child_id = installed.get(slot.id, "")
            if not child_id:
                continue
            out.append((slot.id, child_id))
            walk(child_id)

    walk(gun.id)
    return out


def compatible_ammo_id(gun: WbItem, ammo_id: str | None) -> str | None:
    ammo = (ammo_id or "").strip()
    if not ammo:
        return None
    if gun.allowed_ammo and ammo not in gun.allowed_ammo:
        return None
    return ammo


def validate_build(
    index: WorkbenchIndex,
    gun: WbItem,
    pairs: list[tuple[str, str]],
    ammo_id: str | None = None,
) -> None:
    """拒绝不属于该槽的配件、以及枪械不允许的弹药。"""
    for slot_id, item_id in _pairs_map(pairs).items():
        slot = index.slots.get(slot_id)
        if slot is None:
            raise TarkovWorkbenchError("槽位无效", status_code=400)
        if item_id not in slot.allowed_ids:
            raise TarkovWorkbenchError("配件不属于该槽位", status_code=400)
    ammo = (ammo_id or "").strip()
    if ammo and gun.allowed_ammo and ammo not in gun.allowed_ammo:
        raise TarkovWorkbenchError("弹药不适用该枪", status_code=400)


def calculate(
    db: Session,
    gun_id: str,
    pairs: list[tuple[str, str]],
    ammo_id: str | None = None,
) -> dict[str, Any]:
    index = load_index(db)
    gun = _require_gun(index, gun_id)
    validate_build(index, gun, pairs, ammo_id)
    installed = _pairs_map(pairs)
    stats = calculate_stats(index, gun.id, pairs, ammo_id)
    return {
        "slots": build_slot_tree(index, gun.id, installed),
        "stats": stats,
    }
