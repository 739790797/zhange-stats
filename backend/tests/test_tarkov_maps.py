"""Unit tests for tarkov map projection / aliases."""

from __future__ import annotations

import time

from app.services.tarkov.bosses import map_xyz
from app.services.tarkov.maps import (
    FACTORY_EXIT_KEY_ID,
    HUB_SKIP,
    _apply_map_markers,
    _fill_item_refs,
    _marker_cache,
    _marker_cache_key,
    classify_map_spawn,
    enrich_lock_keys,
    factory_exit_key_lock_allowed,
    parse_map_rows,
    resolve_map_slug,
)


def _payload() -> dict:
    return {
        "maps": {
            "factory": {
                "id": "factory",
                "name": "Factory",
                "normalizedName": "factory",
                "raidDuration": 20,
                "players": "4-6",
                "wiki": "https://wiki/factory",
                "extracts": [
                    {"id": "e1", "name": "Gate 3", "faction": "pmc"},
                    {"id": "e2", "name": "Cellars", "faction": "scav"},
                ],
                "transits": [
                    {
                        "id": "15",
                        "description": "WOO_TRANSIT_15_DESC",
                        "position": {"x": 8, "y": 0, "z": 9},
                    }
                ],
                "bosses": [{"mob": "bossTagilla", "spawnChance": 0.3}],
            },
            "night-factory": {
                "id": "night-factory",
                "name": "Factory",
                "normalizedName": "night-factory",
                "raidDuration": 25,
                "players": "4-5",
                "parent": "factory",
            },
            "the-lab": {
                "id": "thelab",
                "name": "The Lab",
                "normalizedName": "the-lab",
                "raidDuration": 40,
                "players": "6-10",
            },
            "streets-of-tarkov": {
                "id": "streets",
                "name": "Streets of Tarkov",
                "normalizedName": "streets-of-tarkov",
                "raidDuration": 50,
                "players": "9-16",
            },
            "openworld": {
                "id": "openworld",
                "name": "Openworld",
                "normalizedName": "openworld",
            },
        },
        "mobs": {
            "bossTagilla": {
                "id": "bossTagilla",
                "name": "Tagilla",
                "normalizedName": "tagilla",
            }
        },
        "locale": {
            "thelab Name": "实验室",
            "Gate 3": "3 号门",
            "WOO_TRANSIT_15_DESC": "前往海关",
        },
    }


def test_resolve_map_slug_aliases() -> None:
    assert resolve_map_slug("lab") == "the-lab"
    assert resolve_map_slug("streets") == "streets-of-tarkov"
    assert resolve_map_slug("labyrinth") == "the-labyrinth"
    assert resolve_map_slug("factory-night") == "night-factory"
    assert resolve_map_slug("customs") == "customs"


def test_parse_map_rows_variants_and_extracts() -> None:
    rows = parse_map_rows(_payload())
    by_slug = {str(r["slug"]): r for r in rows}
    assert "factory" in by_slug
    assert by_slug["night-factory"]["parent_slug"] == "factory"
    assert by_slug["openworld"]["slug"] in HUB_SKIP
    factory = by_slug["factory"]
    assert factory["raid_duration"] == 20
    assert factory["players"] == "4-6"
    assert factory["thumb_link"] == "https://assets.tarkov.dev/maps/svg/Factory.svg"
    assert by_slug["night-factory"]["thumb_link"] == factory["thumb_link"]
    assert by_slug["the-lab"]["thumb_link"].endswith("/labs_v4/1st/0/0/0.png")
    assert factory["interactive_url"].endswith("/map/factory")
    names = {row["name"] for row in factory["extracts"]}
    assert "3 号门" in names
    transit = next(row for row in factory["extracts"] if row["id"] == "transit:15")
    assert transit["name"] == "前往海关"
    assert transit["faction"] == "转图"
    assert transit["x"] == 8
    assert transit["z"] == 9
    bosses = factory["bosses"]
    assert bosses and bosses[0]["slug"] == "tagilla"
    assert bosses[0]["kind"] == "boss"
    assert bosses[0]["spawn_chance"] == 30


def test_map_bosses_mark_soldiers() -> None:
    payload = _payload()
    payload["maps"]["factory"]["bosses"] = [
        {"mob": "bossTagilla", "spawnChance": 0.3},
        {"mob": "vsRF", "spawnChance": 1},
    ]
    payload["mobs"]["vsRF"] = {
        "id": "vsRF",
        "name": "vsRF",
        "normalizedName": "af",
    }
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    by_id = {str(row["id"]): row for row in factory["bosses"]}
    assert by_id["vsRF"]["kind"] == "soldier"
    assert by_id["vsRF"]["slug"] == "vs-rf"
    assert by_id["bossTagilla"]["kind"] == "boss"


def test_map_xyz_nested_and_array() -> None:
    assert map_xyz({"position": {"x": 1, "y": 2, "z": 3}}) == {
        "x": 1.0,
        "y": 2.0,
        "z": 3.0,
    }
    assert map_xyz([10, 4, -2]) == {"x": 10.0, "y": 4.0, "z": -2.0}
    assert map_xyz({"name": "Gate"}) is None


def test_parse_map_rows_keeps_extract_and_boss_coords() -> None:
    payload = _payload()
    payload["maps"]["factory"]["extracts"][0]["position"] = {
        "x": 100.5,
        "y": 2,
        "z": -30,
    }
    payload["maps"]["factory"]["bosses"][0]["spawnLocations"] = [
        {
            "name": "Shop",
            "chance": 1,
            "positions": [{"x": 3, "y": 0, "z": 4}],
        }
    ]
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    gate = next(row for row in factory["extracts"] if row["id"] == "e1")
    assert gate["x"] == 100.5
    assert gate["z"] == -30
    locs = factory["bosses"][0]["locations"]
    assert locs and locs[0]["positions"][0]["x"] == 3


def test_apply_map_markers_fills_missing_coords() -> None:
    factory = {str(r["slug"]): r for r in parse_map_rows(_payload())}["factory"]
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "extracts": [
                    {
                        "id": "e1",
                        "name": "Gate 3",
                        "position": {"x": 10, "y": 1, "z": 20},
                    }
                ],
                "bosses": [
                    {
                        "normalizedName": "tagilla",
                        "spawnLocations": [
                            {
                                "name": "Shop",
                                "chance": 1,
                                "positions": [{"x": 3, "y": 0, "z": 4}],
                            }
                        ],
                    }
                ],
            }
        },
    }
    _apply_map_markers(factory, {"Shop": "商店"})
    gate = next(row for row in factory["extracts"] if row["id"] == "e1")
    assert gate["x"] == 10
    assert gate["z"] == 20
    locs = factory["bosses"][0]["locations"]
    assert locs and locs[0]["positions"][0]["z"] == 4
    assert locs[0]["name"] == "商店"


def test_apply_map_markers_appends_transits_when_coords_exist() -> None:
    factory = {str(r["slug"]): r for r in parse_map_rows(_payload())}["factory"]
    factory["extracts"] = [
        row for row in factory["extracts"] if not str(row.get("id") or "").startswith("transit:")
    ]
    for row in factory["extracts"]:
        row["x"] = 1
        row["z"] = 2
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "extracts": [],
                "transits": [
                    {
                        "id": "99",
                        "description": "WOO_TRANSIT_15_DESC",
                        "position": {"x": 4, "y": 0, "z": 5},
                    }
                ],
            }
        },
    }
    _apply_map_markers(factory, {"WOO_TRANSIT_15_DESC": "前往海关"})
    transit = next(row for row in factory["extracts"] if row["id"] == "transit:99")
    assert transit["name"] == "前往海关"
    assert transit["faction"] == "转图"
    assert transit["x"] == 4
    assert transit["z"] == 5


def test_apply_map_markers_fills_existing_transit_coords() -> None:
    """撤离点已有坐标、转移点已在列表但缺坐标时，仍要从 overlay transits 补点。"""
    factory = {
        "id": "factory",
        "slug": "factory",
        "extracts": [
            {"id": "e1", "name": "Gate 3", "faction": "PMC", "x": 1, "z": 2},
            {"id": "transit:15", "name": "前往海关", "faction": "转图"},
        ],
        "bosses": [],
    }
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "extracts": [
                    {
                        "id": "e1",
                        "name": "Gate 3",
                        "faction": "pmc",
                        "position": {"x": 1, "y": 0, "z": 2},
                    }
                ],
                "transits": [
                    {
                        "id": "15",
                        "description": "WOO_TRANSIT_15_DESC",
                        "position": {"x": 8, "y": 0, "z": 9},
                    }
                ],
            }
        },
    }
    _apply_map_markers(factory, {})
    transit = next(row for row in factory["extracts"] if row["id"] == "transit:15")
    assert transit["x"] == 8
    assert transit["z"] == 9
    assert transit["faction"] == "转图"


def test_classify_map_spawn_pmc_scav_and_skip_boss() -> None:
    assert (
        classify_map_spawn(
            {
                "categories": ["player"],
                "sides": ["pmc"],
                "position": {"x": 1, "y": 0, "z": 2},
            }
        )
        == "pmc"
    )
    assert (
        classify_map_spawn(
            {
                "categories": ["bot"],
                "sides": ["scav"],
                "position": {"x": 1, "y": 0, "z": 2},
            }
        )
        == "scav"
    )
    assert (
        classify_map_spawn(
            {
                "categories": ["boss"],
                "sides": ["scav"],
                "position": {"x": 1, "y": 0, "z": 2},
            }
        )
        is None
    )
    assert (
        classify_map_spawn(
            {
                "categories": ["sniper"],
                "sides": ["scav"],
                "position": {"x": 1, "y": 0, "z": 2},
            }
        )
        == "sniper"
    )


def test_apply_map_markers_fills_spawns_when_extracts_complete() -> None:
    factory = {str(r["slug"]): r for r in parse_map_rows(_payload())}["factory"]
    for row in factory["extracts"]:
        row["x"] = 1
        row["z"] = 2
    assert factory["spawns"] == []
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "extracts": [],
                "transits": [],
                "bosses": [],
                "spawns": [
                    {
                        "zoneName": "ZoneA",
                        "categories": ["player"],
                        "sides": ["pmc"],
                        "position": {"x": 11, "y": 0, "z": 22},
                    },
                    {
                        "zoneName": "ZoneB",
                        "categories": ["bot"],
                        "sides": ["scav"],
                        "position": {"x": 33, "y": 0, "z": 44},
                    },
                    {
                        "zoneName": "BossZone",
                        "categories": ["boss"],
                        "sides": ["scav"],
                        "position": {"x": 55, "y": 0, "z": 66},
                    },
                ],
            }
        },
    }
    _apply_map_markers(factory, {})
    kinds = {row["kind"] for row in factory["spawns"]}
    assert kinds == {"pmc", "scav"}
    pmc = next(row for row in factory["spawns"] if row["kind"] == "pmc")
    assert pmc["x"] == 11
    assert pmc["z"] == 22
    assert pmc["zone_name"] == "ZoneA"


def test_parse_map_rows_projects_lock_and_hazard_coords() -> None:
    payload = _payload()
    payload["maps"]["factory"]["locks"] = [
        {
            "lockType": "door",
            "needsPower": True,
            "key": {
                "id": "dorm-114",
                "name": "Dorm 114 Key",
                "shortName": "Dorm 114",
                "iconLink": "https://assets.tarkov.dev/dorm-114-icon.webp",
            },
            "position": {"x": 12.5, "y": 1, "z": -8},
            "top": 4,
            "bottom": 0,
        }
    ]
    payload["maps"]["factory"]["hazards"] = [
        {
            "hazardType": "minefield",
            "name": "Minefield",
            "position": {"x": 3, "y": 0, "z": 4},
        }
    ]
    payload["maps"]["factory"]["artillery"] = {
        "zones": [{"position": {"x": 9, "y": 2, "z": 7}, "top": 6, "bottom": 1}]
    }
    payload["maps"]["factory"]["lootLoose"] = [
        {"items": [{"id": "rouble"}], "position": {"x": 1, "y": 0, "z": 1}}
    ]
    payload["locale"]["Minefield"] = "雷区"
    payload["locale"]["Dorm 114 Key"] = "宿舍 114"
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    lock = factory["locks"][0]
    assert lock["key_id"] == "dorm-114"
    assert lock["key_name"] == "宿舍 114"
    assert lock["key_icon"] == "https://assets.tarkov.dev/dorm-114-icon.webp"
    assert lock["needs_power"] is True
    assert lock["lock_type"] == "door"
    assert lock["x"] == 12.5
    assert lock["z"] == -8
    assert lock["top"] == 4
    assert lock["bottom"] == 0
    hazards = factory["hazards"]
    assert {row["hazard_type"] for row in hazards} == {"minefield", "mortar"}
    mine = next(row for row in hazards if row["hazard_type"] == "minefield")
    assert mine["name"] == "雷区"
    assert mine["x"] == 3
    assert mine["z"] == 4
    mortar = next(row for row in hazards if row["hazard_type"] == "mortar")
    assert mortar["name"] == "迫击炮"
    assert mortar["x"] == 9
    loose = factory["loot_loose"]
    assert len(loose) == 1
    assert loose[0]["items"][0]["id"] == "rouble"
    assert loose[0]["x"] == 1
    assert loose[0]["z"] == 1
    assert "lootLoose" not in factory


def test_parse_map_rows_lock_key_id_without_locale_stays_empty() -> None:
    payload = _payload()
    payload["maps"]["factory"]["locks"] = [
        {
            "lockType": "door",
            "key": "5448ba0b4bdc2d02308b456c",
            "position": {"x": 1, "y": 0, "z": 2},
        }
    ]
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    lock = factory["locks"][0]
    assert lock["key_id"] == "5448ba0b4bdc2d02308b456c"
    assert lock["key_name"] == ""
    assert lock["key_icon"] == ""


def test_parse_map_rows_lock_key_locale_id_name() -> None:
    payload = _payload()
    payload["maps"]["factory"]["locks"] = [
        {
            "lockType": "door",
            "key": "5448ba0b4bdc2d02308b456c",
            "position": {"x": 1, "y": 0, "z": 2},
        }
    ]
    payload["locale"]["5448ba0b4bdc2d02308b456c Name"] = "工厂钥匙"
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    assert factory["locks"][0]["key_name"] == "工厂钥匙"


def test_parse_map_rows_resolves_stationary_weapon_catalog() -> None:
    payload = _payload()
    payload["stationaryWeapons"] = {
        "5d52cc5ba4b9367408500062": {
            "id": "5d52cc5ba4b9367408500062",
            "name": "5d52cc5ba4b9367408500062 Name",
            "shortName": "5d52cc5ba4b9367408500062 ShortName",
            "normalizedName": "ags-30-30x29mm-automatic-grenade-launcher",
        }
    }
    payload["maps"]["factory"]["stationaryWeapons"] = [
        {
            "stationaryWeapon": "5d52cc5ba4b9367408500062",
            "position": {"x": 1, "y": 2, "z": 3},
        }
    ]
    payload["locale"]["5d52cc5ba4b9367408500062 Name"] = "AGS 30x29毫米自动榴弹发射器"
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    gun = factory["stationary_weapons"][0]
    assert gun["id"] == "5d52cc5ba4b9367408500062"
    assert gun["name"] == "AGS 30x29毫米自动榴弹发射器"
    assert gun["x"] == 1
    assert gun["z"] == 3


def test_parse_map_rows_resolves_btr_stop_locale() -> None:
    payload = _payload()
    payload["maps"]["factory"]["btrStops"] = [
        {
            "name": "Trading/Dialog/PlayerTaxi/TarkovStreets/p3/Name",
            "x": 4,
            "y": 0,
            "z": 5,
        }
    ]
    payload["locale"]["Trading/Dialog/PlayerTaxi/TarkovStreets/p3/Name"] = "市中心"
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    stop = factory["btr_stops"][0]
    assert stop["name"] == "市中心"
    assert stop["x"] == 4
    assert stop["z"] == 5


def test_parse_map_rows_btr_untranslated_key_falls_back() -> None:
    payload = _payload()
    payload["maps"]["factory"]["btrStops"] = [
        {"name": "Trading/Dialog/PlayerTaxi/Unknown/p9/Name", "x": 1, "y": 0, "z": 2}
    ]
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    assert factory["btr_stops"][0]["name"] == "BTR"


def test_parse_map_rows_resolves_loot_container_catalog() -> None:
    payload = _payload()
    payload["lootContainers"] = {
        "578f87a3245977356274f2cb": {
            "id": "578f87a3245977356274f2cb",
            "name": "578f87a3245977356274f2cb Name",
            "normalizedName": "duffle-bag",
        }
    }
    payload["maps"]["factory"]["lootContainers"] = [
        {
            "lootContainer": "578f87a3245977356274f2cb",
            "position": {"x": 1, "y": 0, "z": 2},
        }
    ]
    payload["maps"]["factory"]["lootLoose"] = [
        {"items": [{"id": "rouble"}], "position": {"x": 9, "y": 0, "z": 8}}
    ]
    payload["locale"]["578f87a3245977356274f2cb Name"] = "旅行袋"
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    box = factory["loot_containers"][0]
    assert box["container_id"] == "578f87a3245977356274f2cb"
    assert box["normalized_name"] == "duffle-bag"
    assert box["name"] == "旅行袋"
    assert box["x"] == 1
    assert box["z"] == 2
    loose = factory["loot_loose"]
    assert len(loose) == 1
    assert loose[0]["items"][0]["id"] == "rouble"
    assert loose[0]["x"] == 9
    assert "lootLoose" not in factory


def test_parse_map_rows_can_skip_loot_layers() -> None:
    payload = _payload()
    payload["maps"]["factory"]["lootContainers"] = [
        {"lootContainer": "box", "position": {"x": 1, "y": 0, "z": 2}}
    ]
    payload["maps"]["factory"]["lootLoose"] = [
        {"items": [{"id": "rouble"}], "position": {"x": 9, "y": 0, "z": 8}}
    ]
    factory = {
        str(r["slug"]): r
        for r in parse_map_rows(payload, loot_loose=False, loot_containers=False)
    }["factory"]
    assert factory["loot_containers"] == []
    assert factory["loot_loose"] == []


def test_parse_map_rows_only_slugs_skips_other_maps() -> None:
    payload = _payload()
    payload["maps"]["factory"]["lootLoose"] = [
        {"items": [{"id": "factory-item"}], "position": {"x": 1, "y": 0, "z": 2}}
    ]
    payload["maps"]["streets-of-tarkov"]["lootLoose"] = [
        {"items": [{"id": "streets-item"}], "position": {"x": 3, "y": 0, "z": 4}}
    ]
    rows = parse_map_rows(payload, only_slugs={"factory"})
    by_slug = {str(r["slug"]): r for r in rows}
    assert set(by_slug) == {"factory"}
    loose = by_slug["factory"]["loot_loose"]
    assert loose
    assert loose[0]["items"][0]["id"] == "factory-item"


def test_slim_loot_loose_drops_icon_and_types() -> None:
    from app.services.tarkov.maps import slim_loot_loose_layer

    out = slim_loot_loose_layer(
        [
            {
                "id": "p1",
                "items": [
                    {
                        "id": "5448ba0b4bdc2d02308b456c",
                        "name": "钥匙",
                        "short_name": "Key",
                        "icon_link": "https://example/icon.png",
                        "types": ["keys"],
                        "handbook_ids": ["cat1"],
                    }
                ],
            }
        ]
    )
    item = out[0]["items"][0]
    assert item["id"] == "5448ba0b4bdc2d02308b456c"
    assert item["handbook_ids"] == ["cat1"]
    assert "icon_link" not in item
    assert "types" not in item


def test_apply_map_markers_skips_loot_when_disabled() -> None:
    factory = {str(r["slug"]): r for r in parse_map_rows(_payload())}["factory"]
    factory["loot_loose"] = []
    factory["loot_containers"] = []
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "lootLoose": [
                    {"items": [{"id": "rouble"}], "position": {"x": 3, "y": 0, "z": 4}}
                ],
                "lootContainers": [
                    {
                        "lootContainer": "box",
                        "position": {"x": 1, "y": 0, "z": 2},
                    }
                ],
            }
        },
    }
    _apply_map_markers(factory, loot_loose=False, loot_containers=False)
    assert factory["loot_loose"] == []
    assert factory["loot_containers"] == []


def test_apply_map_markers_fills_lock_coords_when_dump_lacks_them() -> None:
    factory = {str(r["slug"]): r for r in parse_map_rows(_payload())}["factory"]
    factory["locks"] = [
        {
            "id": "lock:dorm-114:door:0",
            "lock_type": "door",
            "needs_power": False,
            "key_id": "dorm-114",
            "key_name": "宿舍 114",
            "key_short_name": "Dorm 114",
        }
    ]
    factory["extracts"] = [
        {"id": "e1", "name": "Gate 3", "faction": "PMC", "x": 1, "z": 2}
    ]
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "locks": [
                    {
                        "lockType": "door",
                        "needsPower": False,
                        "key": {"id": "dorm-114", "name": "Dorm 114 Key"},
                        "position": {"x": 21, "y": 0, "z": 22},
                    }
                ],
            }
        },
    }
    _apply_map_markers(factory, {"Dorm 114 Key": "宿舍 114"})
    lock = factory["locks"][0]
    assert lock["x"] == 21
    assert lock["z"] == 22
    assert lock["key_id"] == "dorm-114"


def test_apply_map_markers_replaces_empty_locks_from_overlay() -> None:
    factory = {str(r["slug"]): r for r in parse_map_rows(_payload())}["factory"]
    for row in factory["extracts"]:
        row["x"] = 1
        row["z"] = 2
    assert factory["locks"] == []
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "locks": [
                    {
                        "lockType": "door",
                        "key": {"id": "pump", "name": "Pumping Station"},
                        "position": {"x": 5, "y": 0, "z": 6},
                    }
                ],
                "lootLoose": [
                    {"items": [{"id": "rouble"}], "position": {"x": 1, "y": 0, "z": 2}}
                ],
            }
        },
    }
    _apply_map_markers(factory, {})
    assert len(factory["locks"]) == 1
    assert factory["locks"][0]["key_id"] == "pump"
    assert factory["locks"][0]["x"] == 5
    assert factory["locks"][0]["z"] == 6
    loose = factory["loot_loose"]
    assert len(loose) == 1
    assert loose[0]["items"][0]["id"] == "rouble"
    assert loose[0]["x"] == 1
    assert loose[0]["z"] == 2
    assert "lootLoose" not in factory


def test_apply_map_markers_fills_lock_key_names() -> None:
    factory = {
        "id": "factory",
        "slug": "factory",
        "extracts": [{"id": "e1", "name": "Gate 3", "faction": "PMC", "x": 1, "z": 2}],
        "bosses": [],
        "locks": [
            {
                "id": "lock:factory-key:door:0",
                "lock_type": "door",
                "needs_power": False,
                "key_id": "5448ba0b4bdc2d02308b456c",
                "key_name": "",
                "key_short_name": "",
                "key_icon": "",
                "x": -19,
                "z": -48,
            }
        ],
    }
    _marker_cache[_marker_cache_key("pvp")] = {
        "at": time.time(),
        "by_slug": {
            "factory": {
                "normalizedName": "factory",
                "locks": [
                    {
                        "lockType": "door",
                        "key": {
                            "id": "5448ba0b4bdc2d02308b456c",
                            "name": "工厂钥匙",
                            "shortName": "工厂",
                            "iconLink": "https://assets.tarkov.dev/factory-icon.webp",
                        },
                        "position": {"x": -19, "y": 1, "z": -48},
                    }
                ],
            }
        },
    }
    _apply_map_markers(factory, {})
    lock = factory["locks"][0]
    assert lock["key_name"] == "工厂钥匙"
    assert lock["key_short_name"] == "工厂"
    assert lock["key_icon"] == "https://assets.tarkov.dev/factory-icon.webp"
    assert lock["x"] == -19


def test_enrich_lock_keys_from_item_catalog() -> None:
    locks = [
        {
            "key_id": "5448ba0b4bdc2d02308b456c",
            "key_name": "",
            "key_short_name": "",
            "key_icon": "",
        }
    ]
    enrich_lock_keys(
        locks,
        {
            "5448ba0b4bdc2d02308b456c": {
                "id": "5448ba0b4bdc2d02308b456c",
                "name": "工厂钥匙",
                "short_name": "工厂",
                "icon_link": "https://assets.tarkov.dev/factory-icon.webp",
            }
        },
    )
    assert locks[0]["key_name"] == "工厂钥匙"
    assert locks[0]["key_icon"] == "https://assets.tarkov.dev/factory-icon.webp"


def test_parse_map_rows_extract_outline_switches_transfer_and_botom() -> None:
    payload = _payload()
    payload["maps"]["factory"]["extracts"] = [
        {
            "id": "zb013",
            "name": "ZB-013",
            "faction": "pmc",
            "position": {"x": 10, "y": 2, "z": 20},
            "top": 6,
            "bottom": 0,
            "outline": [
                {"x": 9, "y": 2, "z": 19},
                {"x": 11, "y": 2, "z": 19},
                {"x": 11, "y": 2, "z": 21},
            ],
            "switches": ["sw-unlock"],
            "switch": "sw-unlock",
            "transferItem": {"item": "roubles", "count": 20000},
        }
    ]
    payload["maps"]["factory"]["switches"] = [
        {
            "id": "sw-unlock",
            "name": "Pumping Station",
            "activatedBy": False,
            "activates": [{"operation": "Unlock", "extract": "zb013"}],
            "position": {"x": 4, "y": 1, "z": 5},
        },
        {
            "id": "sw-slave",
            "name": "Lab Elevator",
            "activatedBy": "sw-unlock",
            "activates": [{"operation": "Activate", "switch": "sw-unlock"}],
            "position": {"x": 1, "y": 0, "z": 2},
        },
    ]
    payload["maps"]["factory"]["artillery"] = {
        "zones": [
            {
                "position": {"x": 9, "y": 2, "z": 7},
                "top": 6,
                "botom": 1,
                "outline": [
                    {"x": 8, "y": 2, "z": 6},
                    {"x": 10, "y": 2, "z": 6},
                    {"x": 10, "y": 2, "z": 8},
                ],
            }
        ]
    }
    payload["maps"]["factory"]["lootLoose"] = [
        {"items": ["roubles", "bandage"], "position": {"x": 3, "y": 0, "z": 4}}
    ]
    payload["maps"]["factory"]["spawns"] = [
        {
            "categories": ["sniper"],
            "sides": ["scav"],
            "zoneName": "Sniper",
            "position": {"x": 30, "y": 8, "z": 40},
        }
    ]
    payload["locale"]["Pumping Station"] = "泵站"
    payload["locale"]["ZB-013"] = "ZB-013"
    payload["locale"]["roubles Name"] = "卢布"
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    extract = next(row for row in factory["extracts"] if row["id"] == "zb013")
    assert extract["top"] == 6
    assert extract["bottom"] == 0
    assert extract["outline"][0]["x"] == 9
    assert extract["switches"] == [{"id": "sw-unlock", "name": "泵站"}]
    assert extract["transfer_item"]["id"] == "roubles"
    assert extract["transfer_item"]["count"] == 20000
    assert extract["transfer_item"]["name"] == "卢布"
    switch = next(row for row in factory["switches"] if row["id"] == "sw-unlock")
    assert switch["activates"] == [
        {"operation": "Unlock", "name": "ZB-013", "kind": "extract"}
    ]
    slave = next(row for row in factory["switches"] if row["id"] == "sw-slave")
    assert slave["activated_by"] == "泵站"
    assert slave["activates"][0]["kind"] == "switch"
    assert slave["activates"][0]["name"] == "泵站"
    mortar = next(row for row in factory["hazards"] if row["hazard_type"] == "mortar")
    assert mortar["bottom"] == 1
    assert len(mortar["outline"]) == 3
    loose = factory["loot_loose"][0]
    assert [item["id"] for item in loose["items"]] == ["roubles", "bandage"]
    assert loose["items"][0]["name"] == "卢布"
    assert loose["items"][0]["handbook_ids"] == []
    assert factory["spawns"][0]["kind"] == "sniper"
    assert factory["spawns"][0]["x"] == 30


def test_factory_exit_lock_snaps_to_med_tent_gate() -> None:
    payload = _payload()
    payload["maps"]["factory"]["extracts"] = [
        {"id": "e1", "name": "Gate 3", "faction": "pmc", "position": {"x": 58, "y": 3, "z": 63}},
        {
            "id": "7bb46d641d59983a58440a7a58d65933d981c211",
            "name": "Gate m",
            "faction": "pmc",
            "position": {"x": -17.5257778, "y": 1.99233329, "z": -61.27189},
        },
        {
            "id": "cellars",
            "name": "Cellars",
            "faction": "pmc",
            "position": {"x": 73.89422, "y": -3.2876668, "z": -29.0818882},
        },
    ]
    payload["maps"]["factory"]["locks"] = [
        {
            "lockType": "door",
            "key": FACTORY_EXIT_KEY_ID,
            "position": {"x": -19.077774, "y": 1.44520187, "z": -48.57139},
        },
        {
            "lockType": "door",
            "key": FACTORY_EXIT_KEY_ID,
            "position": {"x": 66.8279953, "y": -1.60700011, "z": -29.3244076},
        },
        {
            "lockType": "door",
            "key": FACTORY_EXIT_KEY_ID,
            "position": {"x": 29.1163082, "y": 9.08, "z": 36.51697},
        },
    ]
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    locks = factory["locks"]
    assert locks[0]["x"] == -17.5257778
    assert locks[0]["z"] == -61.27189
    assert locks[0]["y"] == 1.99233329
    assert locks[1]["x"] == 66.8279953
    assert locks[1]["z"] == -29.3244076
    assert locks[2]["x"] == 29.1163082
    assert locks[2]["z"] == 36.51697


def test_factory_exit_lock_already_on_med_gate_stays() -> None:
    payload = _payload()
    payload["maps"]["factory"]["extracts"] = [
        {
            "id": "7bb46d641d59983a58440a7a58d65933d981c211",
            "name": "医疗帐篷大门",
            "faction": "pmc",
            "position": {"x": -17.5, "y": 2, "z": -61.3},
        }
    ]
    payload["maps"]["factory"]["locks"] = [
        {
            "lockType": "door",
            "key": FACTORY_EXIT_KEY_ID,
            "position": {"x": -18.0, "y": 1.5, "z": -60.0},
        }
    ]
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    lock = factory["locks"][0]
    assert lock["x"] == -18.0
    assert lock["z"] == -60.0


def test_factory_exit_key_not_shown_on_lighthouse() -> None:
    assert factory_exit_key_lock_allowed("factory", FACTORY_EXIT_KEY_ID) is True
    assert factory_exit_key_lock_allowed("night-factory", FACTORY_EXIT_KEY_ID) is True
    assert factory_exit_key_lock_allowed("customs", FACTORY_EXIT_KEY_ID) is True
    assert factory_exit_key_lock_allowed("interchange", FACTORY_EXIT_KEY_ID) is True
    assert factory_exit_key_lock_allowed("shoreline", FACTORY_EXIT_KEY_ID) is True
    assert factory_exit_key_lock_allowed("lighthouse", FACTORY_EXIT_KEY_ID) is False
    assert factory_exit_key_lock_allowed("streets-of-tarkov", FACTORY_EXIT_KEY_ID) is False
    assert factory_exit_key_lock_allowed("lighthouse", "other-key") is True

    payload = _payload()
    payload["maps"]["lighthouse"] = {
        "id": "lighthouse",
        "name": "Lighthouse",
        "normalizedName": "lighthouse",
        "raidDuration": 40,
        "players": "9-12",
        "locks": [
            {
                "lockType": "trunk",
                "key": FACTORY_EXIT_KEY_ID,
                "position": {"x": 206.0, "y": 3.8, "z": 521.8},
            },
            {
                "lockType": "door",
                "key": "police-truck",
                "position": {"x": 1, "y": 0, "z": 2},
            },
        ],
    }
    payload["locale"]["Lighthouse"] = "灯塔"
    rows = {str(r["slug"]): r for r in parse_map_rows(payload)}
    locks = rows["lighthouse"]["locks"]
    assert [row["key_id"] for row in locks] == ["police-truck"]
    assert locks[0]["x"] == 1
    assert locks[0]["z"] == 2


def test_apply_map_markers_early_return_still_drops_factory_exit_trunks() -> None:
    lighthouse = {
        "id": "lighthouse",
        "slug": "lighthouse",
        "extracts": [{"id": "e1", "name": "Road to Customs", "faction": "PMC", "x": 1, "z": 2}],
        "bosses": [],
        "locks": [
            {
                "id": "lock:factory-exit:trunk:0",
                "lock_type": "trunk",
                "key_id": FACTORY_EXIT_KEY_ID,
                "key_name": "工厂紧急出口钥匙",
                "x": 206.0,
                "z": 521.8,
            },
            {
                "id": "lock:police-truck:door:1",
                "lock_type": "door",
                "key_id": "police-truck",
                "key_name": "警车钥匙",
                "x": 3,
                "z": 4,
            },
        ],
        "spawns": [{"id": "s1", "kind": "pmc", "x": 1, "z": 2}],
        "hazards": [{"id": "h1", "hazard_type": "minefield", "name": "雷区", "x": 1, "z": 2}],
        "switches": [{"id": "sw1", "name": "开关", "x": 1, "z": 2}],
        "stationary_weapons": [{"id": "st1", "name": "机枪", "x": 1, "z": 2}],
        "btr_stops": [{"name": "BTR", "x": 1, "z": 2}],
        "loot_containers": [
            {
                "container_id": "c1",
                "normalized_name": "duffle-bag",
                "name": "旅行袋",
                "x": 1,
                "z": 2,
            }
        ],
        "loot_loose": [{"id": "loose:0", "items": [{"id": "rouble"}], "x": 1, "z": 2}],
    }
    _apply_map_markers(lighthouse, {}, overlay={"lighthouse": {"normalizedName": "lighthouse"}})
    assert [row["key_id"] for row in lighthouse["locks"]] == ["police-truck"]


def test_apply_map_markers_does_not_readd_factory_exit_trunks() -> None:
    lighthouse = {
        "id": "lighthouse",
        "slug": "lighthouse",
        "extracts": [{"id": "e1", "name": "Road to Customs", "faction": "PMC", "x": 1, "z": 2}],
        "bosses": [],
        "locks": [],
        "spawns": [{"id": "s1", "kind": "pmc", "x": 1, "z": 2}],
        "hazards": [{"id": "h1", "hazard_type": "minefield", "name": "雷区", "x": 1, "z": 2}],
        "switches": [{"id": "sw1", "name": "开关", "x": 1, "z": 2}],
        "stationary_weapons": [{"id": "st1", "name": "机枪", "x": 1, "z": 2}],
        "btr_stops": [{"name": "BTR", "x": 1, "z": 2}],
        "loot_containers": [
            {
                "container_id": "c1",
                "normalized_name": "duffle-bag",
                "name": "旅行袋",
                "x": 1,
                "z": 2,
            }
        ],
        "loot_loose": [{"id": "loose:0", "items": [{"id": "rouble"}], "x": 1, "z": 2}],
    }
    _apply_map_markers(
        lighthouse,
        {},
        overlay={
            "lighthouse": {
                "normalizedName": "lighthouse",
                "locks": [
                    {
                        "lockType": "trunk",
                        "key": FACTORY_EXIT_KEY_ID,
                        "position": {"x": 206.0, "y": 3.8, "z": 521.8},
                    },
                    {
                        "lockType": "door",
                        "key": "police-truck",
                        "position": {"x": 3, "y": 0, "z": 4},
                    },
                ],
            }
        },
    )
    assert [row["key_id"] for row in lighthouse["locks"]] == ["police-truck"]
    assert lighthouse["locks"][0]["x"] == 3
    assert lighthouse["locks"][0]["z"] == 4


def test_factory_exit_lock_does_not_pull_office_across_map() -> None:
    payload = _payload()
    payload["maps"]["factory"]["extracts"] = [
        {
            "name": "Gate m",
            "faction": "pmc",
            "position": {"x": -17.5, "y": 2, "z": -61.3},
        }
    ]
    payload["maps"]["factory"]["locks"] = [
        {
            "lockType": "door",
            "key": FACTORY_EXIT_KEY_ID,
            "position": {"x": 29.1, "y": 9.08, "z": 36.5},
        }
    ]
    factory = {str(r["slug"]): r for r in parse_map_rows(payload)}["factory"]
    lock = factory["locks"][0]
    assert lock["x"] == 29.1
    assert lock["z"] == 36.5


def test_fill_item_refs_copies_handbook_ids() -> None:
    refs = [{"id": "roubles", "name": "", "types": [], "handbook_ids": []}]
    _fill_item_refs(
        refs,
        {
            "roubles": {
                "id": "roubles",
                "name": "卢布",
                "short_name": "RUB",
                "icon_link": "https://icon",
                "types": ["money"],
                "handbook_ids": ["5b47574386f77428ca22b2f1"],
            }
        },
    )
    assert refs[0]["name"] == "卢布"
    assert refs[0]["types"] == ["money"]
    assert refs[0]["handbook_ids"] == ["5b47574386f77428ca22b2f1"]
