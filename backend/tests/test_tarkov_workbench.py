"""Unit tests for tarkov weapon workbench index / stats."""

from __future__ import annotations

import pytest

from app.services.tarkov import workbench as svc


def _payload() -> dict:
    return {
        "data": {
            "items": {
                "gun1": {
                    "id": "gun1",
                    "name": "gun1 Name",
                    "shortName": "TR",
                    "weight": 1.0,
                    "types": ["gun"],
                    "iconLink": "https://x/gun.png",
                    "image512pxLink": "https://x/gun-512.png",
                    "lastLowPrice": 20000,
                    "buyFromTrader": [{"priceRUB": 18000, "trader": "mechanic"}],
                    "categories": ["cat-gun"],
                    "properties": {
                        "propertiesType": "ItemPropertiesWeapon",
                        "caliber": "Caliber545x39",
                        "ergonomics": 40,
                        "recoilVertical": 100,
                        "recoilHorizontal": 200,
                        "sightingRange": 200,
                        "defaultPreset": "preset1",
                        "defaultAmmo": "ammo1",
                        "allowedAmmo": ["ammo1"],
                        "slots": [
                            {
                                "id": "slot-grip",
                                "name": "Pistol Grip",
                                "nameId": "mod_pistol_grip",
                                "required": True,
                                "filters": {
                                    "allowedItems": ["grip1"],
                                    "allowedCategories": ["cat-grip"],
                                },
                            },
                            {
                                "id": "slot-stock",
                                "name": "Stock",
                                "nameId": "mod_stock",
                                "required": False,
                                "filters": {"allowedItems": ["stock1"]},
                            },
                        ],
                    },
                },
                "preset1": {
                    "id": "preset1",
                    "types": ["preset"],
                    "image512pxLink": "https://x/preset-512.png",
                    "containsItems": [{"item": "grip1"}, {"item": "stock1"}, {"item": "rail1"}],
                    "properties": {
                        "propertiesType": "ItemPropertiesPreset",
                        "baseItem": "gun1",
                        "ergonomics": 56,
                        "recoilVertical": 90,
                    },
                },
                "grip1": {
                    "id": "grip1",
                    "name": "grip1 Name",
                    "weight": 0.1,
                    "ergonomicsModifier": 8,
                    "types": ["mods"],
                    "categories": ["cat-grip"],
                    "lastLowPrice": 3000,
                    "properties": {
                        "propertiesType": "ItemPropertiesWeaponMod",
                        "recoilModifier": -0.02,
                        "slots": [
                            {
                                "id": "slot-rail",
                                "name": "Rail",
                                "nameId": "mod_tactical",
                                "required": False,
                                "filters": {"allowedItems": ["rail1"]},
                            }
                        ],
                    },
                },
                "grip2": {
                    "id": "grip2",
                    "name": "grip2 Name",
                    "weight": 0.12,
                    "ergonomicsModifier": 5,
                    "types": ["mods"],
                    "categories": ["cat-grip"],
                    "conflictingItems": ["stock1"],
                    "properties": {
                        "propertiesType": "ItemPropertiesWeaponMod",
                        "recoilModifier": 0,
                    },
                },
                "stock1": {
                    "id": "stock1",
                    "name": "stock1 Name",
                    "weight": 0.4,
                    "ergonomicsModifier": 4,
                    "types": ["mods"],
                    "lastLowPrice": 5000,
                    "properties": {
                        "propertiesType": "ItemPropertiesWeaponMod",
                        "recoilModifier": -0.08,
                    },
                },
                "rail1": {
                    "id": "rail1",
                    "name": "rail1 Name",
                    "weight": 0.05,
                    "ergonomicsModifier": 1,
                    "types": ["mods"],
                    "properties": {
                        "propertiesType": "ItemPropertiesWeaponMod",
                        "recoilModifier": 0,
                    },
                },
                "ammo1": {
                    "id": "ammo1",
                    "name": "ammo1 Name",
                    "weight": 0.01,
                    "types": ["ammo"],
                    "lastLowPrice": 100,
                    "properties": {
                        "propertiesType": "ItemPropertiesAmmo",
                        "caliber": "Caliber545x39",
                    },
                },
                "mag1": {
                    "id": "mag1",
                    "name": "mag1 Name",
                    "weight": 0.2,
                    "types": ["mods"],
                    "properties": {
                        "propertiesType": "ItemPropertiesMagazine",
                        "capacity": 30,
                    },
                },
            }
        },
        "locale": {
            "gun1 Name": "测试步枪",
            "grip1 Name": "握把甲",
            "grip2 Name": "握把乙",
            "stock1 Name": "枪托",
            "rail1 Name": "导轨",
            "ammo1 Name": "测试弹",
            "mag1 Name": "弹匣",
        },
    }


@pytest.fixture
def index() -> svc.WorkbenchIndex:
    return svc.build_index("json.tarkov.dev", _payload())


def test_build_index_maps_slots_and_category_allow(index: svc.WorkbenchIndex):
    gun = index.items["gun1"]
    assert gun.is_weapon
    assert gun.name == "测试步枪"
    assert not index.items["preset1"].is_weapon
    grip_slot = next(s for s in gun.slots if s.id == "slot-grip")
    assert "grip1" in grip_slot.allowed_ids
    assert "grip2" in grip_slot.allowed_ids
    assert index.slots["slot-rail"].parent_item_id == "grip1"


def test_map_factory_pairs_nests_child_slots(index: svc.WorkbenchIndex):
    pairs = svc.map_factory_pairs(index, "gun1")
    assert ("slot-grip", "grip1") in pairs
    assert ("slot-stock", "stock1") in pairs
    assert ("slot-rail", "rail1") in pairs


def test_require_gun_resolves_default_preset_id(index: svc.WorkbenchIndex):
    gun = svc._require_gun(index, "preset1")
    assert gun.id == "gun1"
    assert gun.is_weapon
    pairs = svc.map_factory_pairs(index, "preset1")
    assert ("slot-grip", "grip1") in pairs
    assert ("slot-stock", "stock1") in pairs
    assert ("slot-rail", "rail1") in pairs


def test_calculate_stats_sums_mods(index: svc.WorkbenchIndex):
    pairs = [("slot-grip", "grip1"), ("slot-stock", "stock1")]
    stats = svc.calculate_stats(index, "gun1", pairs, ammo_id=None)
    assert stats["ergonomics"] == 52
    assert stats["recoil_vertical"] == 90
    assert stats["recoil_horizontal"] == 180
    assert stats["weight"] == pytest.approx(1.5)
    assert stats["price_rub"] == 18000 + 3000 + 5000
    assert stats["conflicts"] == []


def test_calculate_stats_flags_conflicts(index: svc.WorkbenchIndex):
    stats = svc.calculate_stats(
        index,
        "gun1",
        [("slot-grip", "grip2"), ("slot-stock", "stock1")],
    )
    assert "grip2" in stats["conflicts"]
    assert "stock1" in stats["conflicts"]
    assert svc.item_summary(index.items["grip2"])["conflicting_ids"] == ["stock1"]


def test_calculate_unknown_gun(index: svc.WorkbenchIndex):
    with pytest.raises(svc.TarkovWorkbenchError, match="未找到枪械"):
        svc.calculate_stats(index, "nope", [])


def test_build_slot_tree_installs_children(index: svc.WorkbenchIndex):
    installed = {"slot-grip": "grip1", "slot-rail": "rail1"}
    tree = svc.build_slot_tree(index, "gun1", installed)
    grip = next(n for n in tree if n["id"] == "slot-grip")
    assert grip["installed"]["id"] == "grip1"
    assert grip["children"][0]["id"] == "slot-rail"
    assert grip["children"][0]["installed"]["id"] == "rail1"


def test_ammo_weight_with_magazine(index: svc.WorkbenchIndex):
    index.items["gun1"].slots.append(
        svc.WbSlot(
            id="slot-mag",
            name="Mag",
            name_id="mod_magazine",
            required=True,
            parent_item_id="gun1",
            allowed_ids=["mag1"],
        )
    )
    stats = svc.calculate_stats(
        index,
        "gun1",
        [("slot-mag", "mag1")],
        ammo_id="ammo1",
    )
    assert stats["mag_capacity"] == 30
    assert stats["weight"] == pytest.approx(1.0 + 0.2 + 0.01 * 30)


def test_validate_build_rejects_illegal_mod_and_ammo(index: svc.WorkbenchIndex):
    gun = index.items["gun1"]
    svc.validate_build(index, gun, [("slot-grip", "grip1")], ammo_id="ammo1")
    with pytest.raises(svc.TarkovWorkbenchError) as illegal_mod:
        svc.validate_build(index, gun, [("slot-grip", "stock1")])
    assert illegal_mod.value.status_code == 400
    with pytest.raises(svc.TarkovWorkbenchError) as missing_slot:
        svc.validate_build(index, gun, [("slot-missing", "grip1")])
    assert missing_slot.value.status_code == 400
    with pytest.raises(svc.TarkovWorkbenchError) as illegal_ammo:
        svc.validate_build(index, gun, [], ammo_id="ammo-other")
    assert illegal_ammo.value.status_code == 400
