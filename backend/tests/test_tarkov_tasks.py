"""Unit tests for tarkov task parse / filter / pagination."""

from __future__ import annotations

from app.services.tarkov import tasks as tasks

PRAPOR = "54cb50c76803fa8b248b4571"
THERAPIST = "54cb57776803fa99248b456e"
STREETS = "5714dc692459777137212e12"
GROUND_ZERO = "653e6760052c01c1c805532f"
CUSTOMS = "56f40101d2720b2a4d8b45d6"


def _envelope() -> dict:
    return {
        "tasks": {
            "t1": {
                "id": "t1",
                "name": "t1 name",
                "normalizedName": "debut",
                "trader": PRAPOR,
                "map": STREETS,
                "minPlayerLevel": 1,
                "experience": 1200,
                "kappaRequired": True,
                "lightkeeperRequired": False,
                "factionName": "Any",
                "wikiLink": "https://wiki/t1",
                "taskImageLink": "https://img/t1.webp",
                "objectives": [
                    {
                        "id": "o1",
                        "type": "visit",
                        "description": "o1",
                        "optional": False,
                        "requiredKeys": [["key1"]],
                    },
                    {
                        "id": "o2",
                        "type": "giveItem",
                        "description": "o2",
                        "optional": True,
                        "item": "item1",
                        "count": 3,
                    },
                ],
                "taskRequirements": [{"task": "t2", "status": ["complete"]}],
                "traderRequirements": [
                    {
                        "trader": THERAPIST,
                        "requirementType": "level",
                        "value": 2,
                    }
                ],
                "finishRewards": {
                    "items": [{"item": "item1", "count": 2}],
                    "traderStanding": [{"trader": PRAPOR, "standing": 0.05}],
                },
                "neededKeys": [{"map": STREETS, "keys": ["key1"]}],
            },
            "t2": {
                "id": "t2",
                "name": "t2 name",
                "normalizedName": "checking",
                "trader": PRAPOR,
                "map": None,
                "minPlayerLevel": 5,
                "experience": 800,
                "kappaRequired": False,
                "objectives": [],
                "taskRequirements": [],
                "finishRewards": {"items": []},
            },
            "t3": {
                "id": "t3",
                "name": "Shortage",
                "trader": THERAPIST,
                "map": CUSTOMS,
                "minPlayerLevel": 2,
                "kappaRequired": False,
                "objectives": [],
            },
        },
        "locale": {
            "t1 name": "首秀",
            "t2 name": "验收",
            "o1": "前往中心区",
            "o2": "上交物品",
        },
    }


def test_parse_locale_and_trader_map():
    rows = tasks.parse_task_rows(_envelope())
    by_id = {r["id"]: r for r in rows}
    assert by_id["t1"]["name"] == "首秀"
    assert by_id["t1"]["trader_slug"] == "prapor"
    assert by_id["t1"]["trader_name"] == "Prapor（俄商）"
    assert by_id["t1"]["map_name"] == "塔科夫街区"
    assert by_id["t1"]["objective_count"] == 2
    assert by_id["t1"]["objective_types"] == ["visit", "giveItem"]
    assert by_id["t1"]["min_trader_level"] == 1
    assert by_id["t2"]["objective_types"] == []
    assert by_id["t2"]["name"] == "验收"
    assert by_id["t2"]["min_trader_level"] == 1
    assert by_id["t3"]["trader_slug"] == "therapist"
    assert by_id["t3"]["map_name"] == "海关"
    assert by_id["t3"]["min_trader_level"] == 1


def test_garbled_zh_locale_falls_back_to_english_name():
    payload = {
        "tasks": {
            "t1": {
                "id": "t1",
                "name": "Debut",
                "normalizedName": "debut",
                "trader": PRAPOR,
                "map": STREETS,
                "objectives": [],
            }
        },
        "locale": {"t1 name": "????", "t1 Name": "？？？？"},
    }
    rows = tasks.parse_task_rows(payload)
    assert rows[0]["name"] == "Debut"


def test_garbled_graphql_name_uses_normalized():
    raw = {
        "id": "t1",
        "name": "????",
        "normalizedName": "checking",
        "trader": PRAPOR,
        "objectives": [],
    }
    row = tasks.project_task_summary(raw, {})
    assert row is not None
    assert row["name"] == "checking"

def test_task_min_trader_level_uses_own_trader():
    assert (
        tasks.task_min_trader_level(
            {
                "traderRequirements": [
                    {
                        "trader": THERAPIST,
                        "requirementType": "level",
                        "value": 2,
                    },
                    {
                        "trader": PRAPOR,
                        "requirementType": "loyaltyLevel",
                        "value": 3,
                    },
                ]
            },
            PRAPOR,
        )
        == 3
    )


def test_task_min_trader_level_defaults_when_only_other_trader():
    assert (
        tasks.task_min_trader_level(
            {
                "traderRequirements": [
                    {
                        "trader": THERAPIST,
                        "requirementType": "level",
                        "value": 2,
                    }
                ]
            },
            PRAPOR,
        )
        == 1
    )


def test_task_min_trader_level_reads_legacy_level_field():
    assert (
        tasks.task_min_trader_level(
            {
                "traderLevelRequirements": [
                    {"trader": PRAPOR, "level": 4},
                ]
            },
            PRAPOR,
        )
        == 4
    )


def test_task_min_trader_level_ignores_reputation():
    assert (
        tasks.task_min_trader_level(
            {
                "traderRequirements": [
                    {
                        "trader": PRAPOR,
                        "requirementType": "reputation",
                        "value": 2,
                    }
                ]
            },
            PRAPOR,
        )
        == 1
    )


def test_unique_objective_types_skips_blank_and_dupes():
    assert tasks.unique_objective_types(
        [
            {"type": "visit"},
            {"type": "visit"},
            {"type": ""},
            {"type": "shoot"},
            "nope",
        ]
    ) == ["visit", "shoot"]


def test_filter_trader_search():
    rows = tasks.parse_task_rows(_envelope())
    prapor = tasks.filter_task_rows(rows, trader="prapor")
    assert {r["id"] for r in prapor} == {"t1", "t2"}
    hit = tasks.filter_task_rows(rows, q="首秀")
    assert [r["id"] for r in hit] == ["t1"]
    streets = tasks.filter_task_rows(rows, map_slug="streets")
    assert [r["id"] for r in streets] == ["t1"]


def test_paginate_clamps_page():
    rows = [{"id": str(i)} for i in range(5)]
    paged = tasks.paginate_task_rows(rows, page=9, page_size=2)
    assert paged["task_count"] == 5
    assert paged["page"] == 3
    assert paged["page_size"] == 2
    assert [r["id"] for r in paged["items"]] == ["4"]

    empty = tasks.paginate_task_rows([], page=3, page_size=50)
    assert empty["items"] == []
    assert empty["task_count"] == 0
    assert empty["page"] == 1

    capped = tasks.paginate_task_rows(rows, page=1, page_size=1000)
    assert capped["page_size"] == tasks.TASKS_PAGE_SIZE_MAX


def test_project_detail_resolves_locale():
    payload = _envelope()
    raw = payload["tasks"]["t1"]
    detail = tasks.project_task_detail(
        raw,
        payload["locale"],
    )
    assert detail is not None
    assert detail["name"] == "首秀"
    assert detail["objectives"][0]["description"] == "前往中心区"
    assert detail["objectives"][1]["optional"] is True
    assert detail["objectives"][1]["count"] == 3
    assert detail["objectives"][1]["items"][0]["id"] == "item1"
    assert detail["trader_requirements"][0]["slug"] == "therapist"
    assert detail["trader_requirements"][0]["requirement_type"] == "level"
    assert detail["trader_requirements"][0]["value"] == 2
    assert detail["finish_rewards"]["items"][0]["count"] == 2
    assert detail["finish_rewards"]["trader_standing"][0]["slug"] == "prapor"
    assert detail["needed_keys"][0]["map"]["name"] == "塔科夫街区"
    assert detail["objectives"][0]["required_keys"][0][0]["id"] == "key1"


def test_required_keys_or_groups_and_fallback_needed_keys():
    raw = {
        "id": "t4",
        "name": "Need keys",
        "trader": PRAPOR,
        "map": STREETS,
        "objectives": [
            {
                "id": "o3",
                "type": "visit",
                "description": "enter",
                "maps": [STREETS],
                "requiredKeys": [
                    ["keyA", "keyB"],
                    ["keyC"],
                ],
            }
        ],
    }
    detail = tasks.project_task_detail(raw, {})
    assert detail is not None
    groups = detail["objectives"][0]["required_keys"]
    assert [r["id"] for r in groups[0]] == ["keyA", "keyB"]
    assert [r["id"] for r in groups[1]] == ["keyC"]
    needed_ids = [k["id"] for k in detail["needed_keys"][0]["keys"]]
    assert needed_ids == ["keyA", "keyB", "keyC"]


def test_needed_keys_resolve_name_from_quest_items():
    detail = tasks.project_task_detail(
        {
            "id": "t-keys",
            "name": "Keys",
            "trader": PRAPOR,
            "map": STREETS,
            "neededKeys": [
                {"map": STREETS, "keys": ["5a9f913a86f77472bf74a592"]},
            ],
            "objectives": [],
        },
        {},
        quest_items={
            "5a9f913a86f77472bf74a592": {
                "id": "5a9f913a86f77472bf74a592",
                "name": "宿舍 114 钥匙",
                "iconLink": "https://example/k.webp",
            }
        },
    )
    assert detail is not None
    key = detail["needed_keys"][0]["keys"][0]
    assert key["name"] == "宿舍 114 钥匙"
    assert key["icon_link"] == "https://example/k.webp"


def test_apply_item_hits_fills_placeholder_key_names():
    rows = [
        {
            "needed_keys": [
                {
                    "map": {"id": STREETS},
                    "keys": [
                        {
                            "id": "5a9f913a86f77472bf74a592",
                            "name": "5a9f913a86f77472bf74a592",
                            "icon_link": "",
                            "types": [],
                        }
                    ],
                }
            ],
            "objectives": [
                {
                    "items": [
                        {"id": "gold", "name": "gold", "icon_link": "", "types": []}
                    ]
                }
            ],
        }
    ]
    tasks.apply_item_hits_to_details(
        rows,
        {
            "5a9f913a86f77472bf74a592": {
                "name": "宿舍 114 钥匙",
                "icon_link": "https://example/k.webp",
                "types": ["keys"],
            },
            "gold": {"name": "金项链", "icon_link": "g.png", "types": ["barter"]},
        },
    )
    key = rows[0]["needed_keys"][0]["keys"][0]
    item = rows[0]["objectives"][0]["items"][0]
    assert key["name"] == "宿舍 114 钥匙"
    assert key["icon_link"] == "https://example/k.webp"
    assert key["types"] == ["keys"]
    assert item["name"] == "金项链"
    assert item["types"] == ["barter"]


def test_graphql_list_envelope():
    payload = {
        "format": "graphql",
        "data": {
            "tasks": [
                {
                    "id": "g1",
                    "name": "Debut",
                    "normalizedName": "debut",
                    "trader": {
                        "id": PRAPOR,
                        "name": "Prapor",
                        "normalizedName": "prapor",
                    },
                    "map": {
                        "id": STREETS,
                        "name": "Streets of Tarkov",
                        "normalizedName": "streets-of-tarkov",
                    },
                    "minPlayerLevel": 1,
                    "kappaRequired": True,
                    "objectives": [],
                }
            ]
        },
        "locale": {},
    }
    rows = tasks.parse_task_rows(payload)
    assert len(rows) == 1
    assert rows[0]["name"] == "Debut"
    assert rows[0]["trader_slug"] == "prapor"
    assert rows[0]["map_name"] == "塔科夫街区"


def test_unique_traders_keeps_home_order():
    rows = tasks.parse_task_rows(_envelope())
    traders = tasks.unique_traders(rows)
    assert [t["slug"] for t in traders] == ["prapor", "therapist"]


def test_sort_task_rows_trader_then_level():
    rows = [
        {"id": "b", "trader_slug": "b", "min_player_level": 1, "name": "z"},
        {"id": "a2", "trader_slug": "a", "min_player_level": 10, "name": "y"},
        {"id": "a1", "trader_slug": "a", "min_player_level": 1, "name": "x"},
    ]
    ordered = tasks.sort_task_rows(rows)
    assert [r["id"] for r in ordered] == ["a1", "a2", "b"]


def test_normalize_objective_exit_exp_bonus_is_status_not_extract():
    statuses, name = tasks.normalize_objective_exit(
        {
            "exitStatus": ["Survived", "Runner"],
            "exitName": "ExpBonusSurvived&ExpBonusRunner",
        }
    )
    assert statuses == ["Survived", "Runner"]
    assert name == ""


def test_project_extract_and_quest_item():
    detail = tasks.project_task_detail(
        {
            "id": "t5",
            "name": "Privacy",
            "trader": THERAPIST,
            "objectives": [
                {
                    "id": "find",
                    "type": "findQuestItem",
                    "description": "find docs",
                    "questItem": "qi1",
                },
                {
                    "id": "extract",
                    "type": "extract",
                    "description": "leave",
                    "exitStatus": ["Survived"],
                    "exitName": "ExpBonusSurvived&ExpBonusRunner",
                    "count": 1,
                },
            ],
        },
        {},
        quest_items={
            "qi1": {
                "id": "qi1",
                "name": "TerraGroup docs",
                "iconLink": "https://example/qi1.webp",
            }
        },
    )
    assert detail is not None
    find, extract = detail["objectives"]
    assert find["items"][0]["id"] == "qi1"
    assert find["items"][0]["icon_link"] == "https://example/qi1.webp"
    assert extract["exit_status"] == ["Survived", "Runner"]
    assert extract["exit_name"] == ""


def test_map_match_keys_aliases():
    keys, ids = tasks.map_match_keys("streets")
    assert "streets" in keys
    assert "streets-of-tarkov" in keys
    assert STREETS in ids
    lab_keys, _ids = tasks.map_match_keys("lab")
    assert "the-lab" in lab_keys
    customs_keys, customs_ids = tasks.map_match_keys("customs")
    assert "bigmap" in customs_keys
    assert CUSTOMS in customs_ids
    bigmap_keys, bigmap_ids = tasks.map_match_keys("bigmap")
    assert "customs" in bigmap_keys
    assert CUSTOMS in bigmap_ids


def test_map_ids_do_not_swap_streets_and_ground_zero():
    assert tasks.map_info(STREETS) == ("streets", "塔科夫街区")
    assert tasks.map_info(GROUND_ZERO) == ("ground-zero", "中心区")
    _keys, street_ids = tasks.map_match_keys("streets")
    _keys, gz_ids = tasks.map_match_keys("ground-zero")
    assert STREETS in street_ids
    assert GROUND_ZERO not in street_ids
    assert GROUND_ZERO in gz_ids
    assert STREETS not in gz_ids
    payload = {
        "tasks": {
            "gz": {
                "id": "gz",
                "name": "First in Line",
                "trader": PRAPOR,
                "map": GROUND_ZERO,
                "objectives": [{"id": "v", "type": "visit", "maps": [GROUND_ZERO]}],
            },
            "st": {
                "id": "st",
                "name": "Revision Streets",
                "trader": PRAPOR,
                "map": STREETS,
                "objectives": [{"id": "v2", "type": "visit", "maps": [STREETS]}],
            },
        },
        "locale": {},
    }
    _name, streets_rows = tasks.collect_raid_prep_rows(payload, "streets")
    _name, gz_rows = tasks.collect_raid_prep_rows(payload, "ground-zero")
    assert [r["id"] for r in streets_rows] == ["st"]
    assert [r["id"] for r in gz_rows] == ["gz"]


def test_project_zones_and_possible_locations():
    detail = tasks.project_task_detail(
        {
            "id": "t-zone",
            "name": "Visit",
            "trader": PRAPOR,
            "map": STREETS,
            "objectives": [
                {
                    "id": "o-visit",
                    "type": "visit",
                    "description": "go",
                    "maps": [STREETS],
                    "zones": [
                        {
                            "id": "z1",
                            "map": STREETS,
                            "position": {"x": 1.0, "y": 2.0, "z": 3.0},
                            "outline": [
                                {"x": 0, "y": 2, "z": 0},
                                {"x": 2, "y": 2, "z": 0},
                                {"x": 2, "y": 2, "z": 2},
                            ],
                        }
                    ],
                },
                {
                    "id": "o-find",
                    "type": "findQuestItem",
                    "description": "hdd",
                    "possibleLocations": [
                        {
                            "map": STREETS,
                            "positions": [{"x": 10, "z": 20}],
                        }
                    ],
                },
            ],
        },
        {},
    )
    assert detail is not None
    zone = detail["objectives"][0]["zones"][0]
    assert zone["map_slug"] == "streets"
    assert zone["x"] == 1.0
    assert len(zone["outline"]) == 3
    loc = detail["objectives"][1]["possible_locations"][0]
    assert loc["positions"][0]["z"] == 20
    assert tasks.task_hits_map(detail, "streets-of-tarkov") is True
    assert tasks.task_has_map_markers(detail, "streets") is True
    assert tasks.task_hits_map(detail, "customs") is False


def test_collect_raid_prep_rows_filters_map():
    payload = {
        "tasks": {
            "on-map": {
                "id": "on-map",
                "name": "On streets",
                "trader": PRAPOR,
                "map": STREETS,
                "objectives": [{"id": "v", "type": "visit", "maps": [STREETS]}],
            },
            "other": {
                "id": "other",
                "name": "On customs",
                "trader": PRAPOR,
                "map": CUSTOMS,
                "objectives": [{"id": "v2", "type": "visit", "maps": [CUSTOMS]}],
            },
        },
        "locale": {},
    }
    name, rows = tasks.collect_raid_prep_rows(payload, "streets")
    assert name == "塔科夫街区"
    assert [r["id"] for r in rows] == ["on-map"]


def test_project_zones_graphql_map_object():
    detail = tasks.project_task_detail(
        {
            "id": "t-gql",
            "name": "GQL",
            "trader": PRAPOR,
            "objectives": [
                {
                    "id": "o",
                    "type": "shoot",
                    "description": "kill",
                    "zoneNames": ["Dorms"],
                    "zones": [
                        {
                            "id": "zone-a",
                            "map": {
                                "id": STREETS,
                                "name": "Streets of Tarkov",
                                "normalizedName": "streets-of-tarkov",
                            },
                            "position": {"x": 5, "y": 0, "z": 9},
                        }
                    ],
                }
            ],
        },
        {},
    )
    assert detail is not None
    assert detail["objectives"][0]["zone_names"] == ["Dorms"]
    zone = detail["objectives"][0]["zones"][0]
    assert zone["map_id"] == STREETS
    assert zone["map_slug"] == "streets"
    assert zone["x"] == 5
    assert tasks.task_hits_map(detail, "streets-of-tarkov") is True
    assert tasks.task_has_map_markers(detail, "streets") is True


def test_project_zones_drops_duplicate_copies():
    shoreline = "5704e554d2720bac5b8b456e"
    truck = {
        "id": "place_peacemaker_005_N1",
        "map": shoreline,
        "position": {"x": -234.48999, "y": -3.47, "z": -164.42},
        "outline": [
            {"x": -236.8, "y": -3.47, "z": -169.5},
            {"x": -229.3, "y": -3.47, "z": -166.7},
            {"x": -232.1, "y": -3.47, "z": -159.2},
        ],
    }
    flyer_a = {
        "id": "place_flyers1",
        "map": CUSTOMS,
        "position": {"x": 10.1, "z": 20.2},
    }
    flyer_b = {
        "id": "place_flyers1",
        "map": CUSTOMS,
        "position": {"x": 80.0, "z": 90.0},
    }
    detail = tasks.project_task_detail(
        {
            "id": "t-dup",
            "name": "Dup",
            "trader": PRAPOR,
            "objectives": [
                {
                    "id": "o-mark",
                    "type": "mark",
                    "zones": [truck, dict(truck)],
                },
                {
                    "id": "o-fly",
                    "type": "plantItem",
                    "zones": [flyer_a, flyer_b],
                },
            ],
        },
        {},
    )
    assert detail is not None
    assert len(detail["objectives"][0]["zones"]) == 1
    assert detail["objectives"][0]["zones"][0]["id"] == "place_peacemaker_005_N1"
    assert [z["x"] for z in detail["objectives"][1]["zones"]] == [10.1, 80.0]


def test_collect_raid_prep_includes_zone_only_task():
    payload = {
        "tasks": {
            "zonly": {
                "id": "zonly",
                "name": "Zone only",
                "trader": PRAPOR,
                "map": None,
                "objectives": [
                    {
                        "id": "o",
                        "type": "visit",
                        "zones": [
                            {
                                "id": "z",
                                "map": STREETS,
                                "position": {"x": 1, "z": 2},
                            }
                        ],
                    }
                ],
            },
            "nomark": {
                "id": "nomark",
                "name": "Name only",
                "trader": PRAPOR,
                "map": STREETS,
                "objectives": [{"id": "v", "type": "visit", "maps": [STREETS]}],
            },
        },
        "locale": {},
    }
    _name, rows = tasks.collect_raid_prep_rows(payload, "streets")
    assert [r["id"] for r in rows] == ["zonly", "nomark"]
    assert rows[0]["has_map_markers"] is True
    assert rows[1]["has_map_markers"] is False


def test_crop_raid_prep_detail_keeps_other_map_stubs():
    detail = tasks.project_task_detail(
        {
            "id": "multi",
            "name": "Multi",
            "trader": PRAPOR,
            "map": STREETS,
            "objectives": [
                {
                    "id": "o1",
                    "type": "visit",
                    "maps": [STREETS, CUSTOMS],
                    "zones": [
                        {
                            "id": "zs",
                            "map": STREETS,
                            "position": {"x": 1, "z": 2},
                        },
                        {
                            "id": "zc",
                            "map": CUSTOMS,
                            "position": {"x": 9, "z": 9},
                        },
                    ],
                },
                {
                    "id": "o2",
                    "type": "visit",
                    "maps": [CUSTOMS],
                    "zones": [
                        {
                            "id": "only-c",
                            "map": CUSTOMS,
                            "position": {"x": 3, "z": 3},
                        }
                    ],
                },
            ],
        },
        {},
    )
    assert detail is not None
    cropped = tasks.crop_raid_prep_detail_for_map(detail, "streets")
    assert [o["id"] for o in cropped["objectives"]] == ["o1", "o2"]
    assert cropped["objective_count"] == 1
    o1 = cropped["objectives"][0]
    assert [z["id"] for z in o1["zones"]] == ["zs"]
    assert {m.get("slug") for m in o1["maps"]} >= {"streets", "customs"}
    o2 = cropped["objectives"][1]
    assert o2["zones"] == []
    assert o2["possible_locations"] == []
    assert any((m.get("slug") == "customs") for m in o2["maps"])


def test_strip_raid_prep_geometry_keeps_items():
    row = {
        "id": "t1",
        "objectives": [
            {
                "id": "o1",
                "type": "findQuestItem",
                "zones": [{"id": "z1"}],
                "possible_locations": [{"map_slug": "customs"}],
                "items": [{"name": "hdd", "count": 1}],
            }
        ],
    }
    out = tasks.strip_raid_prep_geometry(row)
    assert out["objectives"][0]["zones"] == []
    assert out["objectives"][0]["possible_locations"] == []
    assert out["objectives"][0]["items"] == [{"name": "hdd", "count": 1}]
    assert row["objectives"][0]["zones"] == [{"id": "z1"}]


def test_strip_raid_prep_catalog_drops_objectives():
    row = {
        "id": "t1",
        "name": "Debut",
        "normalized_name": "debut",
        "trader_slug": "prapor",
        "trader_name": "Prapor",
        "has_map_markers": True,
        "min_player_level": 2,
        "objective_count": 1,
        "objective_types": ["visit"],
        "wiki_link": "https://example.test",
        "objectives": [{"id": "o1", "description": "go", "items": [{"name": "hdd"}]}],
        "needed_keys": [{"item_id": "k1"}],
    }
    out = tasks.strip_raid_prep_catalog(row)
    assert out["id"] == "t1"
    assert out["name"] == "Debut"
    assert out["trader_slug"] == "prapor"
    assert out["has_map_markers"] is True
    assert out["objectives"] == []
    assert out["needed_keys"] == []
    assert "wiki_link" not in out
    assert row["objectives"][0]["description"] == "go"


def test_canonical_raid_map_slug():
    assert tasks.canonical_raid_map_slug("streets-of-tarkov") == "streets"
    assert tasks.canonical_raid_map_slug("bigmap") == "customs"
    assert tasks.canonical_raid_map_slug("nope") == "nope"


def test_task_hits_map_customs_name_and_bigmap():
    assert (
        tasks.task_hits_map(
            {
                "id": "t-bigmap",
                "map_id": "",
                "map_slug": "bigmap",
                "map_name": "",
                "objectives": [],
            },
            "customs",
        )
        is True
    )
    assert (
        tasks.task_hits_map(
            {
                "id": "t-name",
                "map_id": "",
                "map_slug": "",
                "map_name": "海关",
                "objectives": [],
            },
            "customs",
        )
        is True
    )
    named_obj = {
        "id": "t-obj",
        "map_id": "",
        "map_slug": "",
        "map_name": "",
        "objectives": [
            {
                "maps": [{"name": "海关"}],
                "zones": [],
                "possible_locations": [],
            }
        ],
    }
    assert tasks.task_hits_map(named_obj, "customs") is True
    assert tasks.task_hits_map(named_obj, "woods") is False


def test_collect_raid_prep_rows_bigmap_alias():
    payload = {
        "tasks": {
            "on-customs": {
                "id": "on-customs",
                "name": "On customs",
                "trader": PRAPOR,
                "map": CUSTOMS,
                "objectives": [{"id": "v", "type": "visit", "maps": [CUSTOMS]}],
            }
        },
        "locale": {},
    }
    name, rows = tasks.collect_raid_prep_rows(payload, "bigmap")
    assert name == "海关"
    assert [r["id"] for r in rows] == ["on-customs"]


def test_collect_raid_prep_task_index_buckets_maps():
    payload = {
        "tasks": {
            "on-map": {
                "id": "on-map",
                "name": "On streets",
                "trader": PRAPOR,
                "map": STREETS,
                "objectives": [{"id": "v", "type": "visit", "maps": [STREETS]}],
            },
            "other": {
                "id": "other",
                "name": "On customs",
                "trader": PRAPOR,
                "map": CUSTOMS,
                "objectives": [{"id": "v2", "type": "visit", "maps": [CUSTOMS]}],
            },
        },
        "locale": {},
    }
    index = tasks.collect_raid_prep_task_index(payload)
    slugs = tasks.raid_prep_room_map_slugs()
    assert "streets" in slugs
    assert "night-factory" in slugs
    assert index["streets"]["on-map"] == "On streets"
    assert "on-map" not in index["customs"]
    assert index["customs"]["other"] == "On customs"
