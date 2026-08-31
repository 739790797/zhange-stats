"""Unit tests for tarkov map projection / aliases."""

from __future__ import annotations

import time

from app.services.tarkov.bosses import map_xyz
from app.services.tarkov.maps import (
    HUB_SKIP,
    _apply_graphql_markers,
    _marker_cache,
    _marker_cache_key,
    classify_map_spawn,
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


def test_apply_graphql_markers_fills_missing_coords() -> None:
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
    _apply_graphql_markers(factory, {"Shop": "商店"})
    gate = next(row for row in factory["extracts"] if row["id"] == "e1")
    assert gate["x"] == 10
    assert gate["z"] == 20
    locs = factory["bosses"][0]["locations"]
    assert locs and locs[0]["positions"][0]["z"] == 4
    assert locs[0]["name"] == "商店"


def test_apply_graphql_markers_appends_transits_when_coords_exist() -> None:
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
    _apply_graphql_markers(factory, {"WOO_TRANSIT_15_DESC": "前往海关"})
    transit = next(row for row in factory["extracts"] if row["id"] == "transit:99")
    assert transit["name"] == "前往海关"
    assert transit["faction"] == "转图"
    assert transit["x"] == 4
    assert transit["z"] == 5


def test_apply_graphql_markers_fills_existing_transit_coords() -> None:
    """撤离点已有坐标、转移点已在列表但缺坐标时，仍要从 GraphQL transits 补点。"""
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
    _apply_graphql_markers(factory, {})
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
        is None
    )


def test_apply_graphql_markers_fills_spawns_when_extracts_complete() -> None:
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
    _apply_graphql_markers(factory, {})
    kinds = {row["kind"] for row in factory["spawns"]}
    assert kinds == {"pmc", "scav"}
    pmc = next(row for row in factory["spawns"] if row["kind"] == "pmc")
    assert pmc["x"] == 11
    assert pmc["z"] == 22
    assert pmc["zone_name"] == "ZoneA"
