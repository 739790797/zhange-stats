"""Unit tests for tarkov task parse / filter / pagination."""

from __future__ import annotations

from app.services.tarkov import tasks as tasks

PRAPOR = "54cb50c76803fa8b248b4571"
THERAPIST = "54cb57776803fa99248b456e"
STREETS = "653e6760052c01c1c805532f"
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
    assert by_id["t1"]["kappa_required"] is True
    assert by_id["t1"]["objective_count"] == 2
    assert by_id["t1"]["objective_types"] == ["visit", "giveItem"]
    assert by_id["t2"]["objective_types"] == []
    assert by_id["t2"]["name"] == "验收"
    assert by_id["t3"]["trader_slug"] == "therapist"
    assert by_id["t3"]["map_name"] == "海关"
    assert by_id["t1"]["task_requirements"][0]["id"] == "t2"
    assert by_id["t1"]["task_requirements"][0]["name"] == "验收"
    assert by_id["t2"]["task_requirements"] == []


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


def test_filter_trader_kappa_search():
    rows = tasks.parse_task_rows(_envelope())
    prapor = tasks.filter_task_rows(rows, trader="prapor")
    assert {r["id"] for r in prapor} == {"t1", "t2"}
    kappa = tasks.filter_task_rows(rows, kappa=True)
    assert [r["id"] for r in kappa] == ["t1"]
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


def test_project_detail_resolves_locale_and_prereq():
    payload = _envelope()
    raw = payload["tasks"]["t1"]
    detail = tasks.project_task_detail(
        raw,
        payload["locale"],
        tasks_by_id=payload["tasks"],
    )
    assert detail is not None
    assert detail["name"] == "首秀"
    assert detail["objectives"][0]["description"] == "前往中心区"
    assert detail["objectives"][1]["optional"] is True
    assert detail["objectives"][1]["count"] == 3
    assert detail["objectives"][1]["items"][0]["id"] == "item1"
    assert detail["task_requirements"][0]["id"] == "t2"
    assert detail["task_requirements"][0]["name"] == "验收"
    assert detail["trader_requirements"][0]["slug"] == "therapist"
    assert detail["trader_requirements"][0]["requirement_type"] == "level"
    assert detail["trader_requirements"][0]["value"] == 2
    t2 = tasks.project_task_detail(
        payload["tasks"]["t2"],
        payload["locale"],
        tasks_by_id=payload["tasks"],
    )
    assert t2 is not None
    assert [r["id"] for r in t2["successor_tasks"]] == ["t1"]
    assert t2["successor_tasks"][0]["name"] == "首秀"
    assert detail["finish_rewards"]["items"][0]["count"] == 2
    assert detail["finish_rewards"]["trader_standing"][0]["slug"] == "prapor"
    assert detail["needed_keys"][0]["map"]["name"] == "塔科夫街区"
    assert detail["objectives"][0]["required_keys"][0][0]["id"] == "key1"


def test_neighborhood_two_hops_and_fork():
    payload = {
        "tasks": {
            "a": {
                "id": "a",
                "name": "A",
                "trader": PRAPOR,
                "taskRequirements": [],
            },
            "b": {
                "id": "b",
                "name": "B",
                "trader": PRAPOR,
                "taskRequirements": [{"task": "a", "status": ["complete"]}],
            },
            "c": {
                "id": "c",
                "name": "C",
                "trader": PRAPOR,
                "taskRequirements": [{"task": "b", "status": ["complete"]}],
            },
            "d": {
                "id": "d",
                "name": "D",
                "trader": PRAPOR,
                "taskRequirements": [{"task": "c", "status": ["complete"]}],
            },
            "fork": {
                "id": "fork",
                "name": "Fork",
                "trader": PRAPOR,
                "taskRequirements": [{"task": "c", "status": ["complete"]}],
            },
        },
        "locale": {"b name": "中段"},
    }
    nb = tasks.build_task_neighborhood("b", payload["tasks"], payload["locale"], hops=2)
    hops = {node["id"]: node["hop"] for node in nb["nodes"]}
    assert hops == {"a": -1, "b": 0, "c": 1, "d": 2, "fork": 2}
    names = {node["id"]: node["name"] for node in nb["nodes"]}
    assert names["b"] == "中段"
    edges = {(row["source_id"], row["target_id"]) for row in nb["edges"]}
    assert edges == {("a", "b"), ("b", "c"), ("c", "d"), ("c", "fork")}

    near = tasks.build_task_neighborhood("b", payload["tasks"], payload["locale"], hops=1)
    assert {node["id"] for node in near["nodes"]} == {"a", "b", "c"}


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


def test_classify_complete_available_locked_failed():
    rows = tasks.parse_task_rows(_envelope())
    by_id = {r["id"]: r for r in rows}
    progress = {
        "player_level": 40,
        "pmc_faction": "BEAR",
        "tasks": {
            "t2": {"complete": True, "failed": False, "invalid": False},
        },
    }
    assert tasks.classify_task_progress(by_id["t3"], progress) == "available"
    assert tasks.classify_task_progress(by_id["t1"], progress) == "available"
    assert tasks.classify_task_progress(by_id["t2"], progress) == "complete"
    locked = tasks.classify_task_progress(
        by_id["t1"],
        {"player_level": 40, "pmc_faction": "BEAR", "tasks": {}},
    )
    assert locked == "locked"
    assert (
        tasks.classify_task_progress(
            by_id["t2"],
            {"player_level": 3, "pmc_faction": "BEAR", "tasks": {}},
        )
        == "locked"
    )
    assert (
        tasks.classify_task_progress(
            by_id["t1"],
            {
                "player_level": 40,
                "pmc_faction": "BEAR",
                "tasks": {"t1": {"complete": True, "failed": False, "invalid": False}},
            },
        )
        == "complete"
    )
    assert (
        tasks.classify_task_progress(
            by_id["t1"],
            {
                "player_level": 40,
                "pmc_faction": "BEAR",
                "tasks": {"t1": {"complete": False, "failed": True, "invalid": False}},
            },
        )
        == "failed"
    )


def test_filter_progress_status():
    rows = tasks.parse_task_rows(_envelope())
    annotated = tasks.annotate_task_progress(
        rows,
        {
            "player_level": 40,
            "pmc_faction": "BEAR",
            "tasks": {"t2": {"complete": True, "failed": False, "invalid": False}},
        },
    )
    available = tasks.filter_task_rows(annotated, progress_status="available")
    assert {r["id"] for r in available} == {"t1", "t3"}
    locked = tasks.filter_task_rows(
        tasks.annotate_task_progress(
            rows, {"player_level": 40, "pmc_faction": "BEAR", "tasks": {}}
        ),
        progress_status="locked",
    )
    assert {r["id"] for r in locked} == {"t1"}


def test_sort_task_rows_progress_order():
    rows = [
        {
            "id": "failed",
            "progress_status": "failed",
            "trader_slug": "a",
            "min_player_level": 1,
            "name": "z",
        },
        {
            "id": "complete",
            "progress_status": "complete",
            "trader_slug": "a",
            "min_player_level": 1,
            "name": "y",
        },
        {
            "id": "locked",
            "progress_status": "locked",
            "trader_slug": "a",
            "min_player_level": 1,
            "name": "x",
        },
        {
            "id": "available",
            "progress_status": "available",
            "trader_slug": "a",
            "min_player_level": 1,
            "name": "w",
        },
    ]
    ordered = tasks.sort_task_rows(rows, by_progress=True)
    assert [r["id"] for r in ordered] == [
        "available",
        "locked",
        "complete",
        "failed",
    ]


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
        include_successors=False,
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
        include_successors=False,
    )
    assert detail is not None
    assert detail["objectives"][0]["zone_names"] == ["Dorms"]
    zone = detail["objectives"][0]["zones"][0]
    assert zone["map_id"] == STREETS
    assert zone["map_slug"] == "streets"
    assert zone["x"] == 5
    assert tasks.task_hits_map(detail, "streets-of-tarkov") is True
    assert tasks.task_has_map_markers(detail, "streets") is True


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
