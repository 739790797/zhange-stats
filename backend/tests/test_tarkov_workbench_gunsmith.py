"""枪匠任务投影 / 对照 / 求解。"""

from __future__ import annotations

from app.services.tarkov import workbench as wb
from app.services.tarkov import workbench_gunsmith as gs
from tests.test_tarkov_workbench import _payload
from tests.test_tarkov_tasks import PRAPOR


def test_constraints_from_attributes():
    out = gs.constraints_from_attributes(
        [
            {"name": "ergonomics", "compare_method": ">=", "value": 45},
            {"name": "recoil", "compare_method": "<=", "value": 850},
            {"name": "weight", "compare_method": "<=", "value": 3.5},
            {"name": "magazineCapacity", "compare_method": ">=", "value": 30},
            {"name": "magazineCapacity", "compare_method": "<=", "value": 10},
            {"name": "effectiveDistance", "compare_method": ">=", "value": 800},
            {"name": "durability", "compare_method": ">=", "value": 60},
            {"name": "width", "compare_method": "<=", "value": 4},
            {"name": "height", "compare_method": "<=", "value": 2},
            {"name": "accuracy", "compare_method": ">=", "value": 0},
            {"name": "weight", "compare_method": ">=", "value": 0},
            {"name": "width", "compare_method": ">=", "value": 4},
        ]
    )
    assert out["min_ergonomics"] == 45
    assert out["max_recoil_sum"] == 850
    assert out["max_weight"] == 3.5
    assert out["min_mag_capacity"] == 30
    assert out["max_mag_capacity"] == 10
    assert out["min_sighting_range"] == 800
    assert out["min_durability"] == 60
    assert out["max_width"] == 4
    assert out["max_height"] == 2
    assert "min_width" not in out
    assert "min_accuracy" not in out


def test_collect_gunsmith_tasks_from_dump():
    payload = {
        "tasks": {
            "gs": {
                "id": "gs",
                "name": "Gunsmith - Part 1",
                "trader": PRAPOR,
                "objectives": [
                    {
                        "id": "o-b",
                        "type": "buildWeapon",
                        "item": "gun1",
                        "containsAll": ["grip1"],
                        "containsCategory": [
                            ["cat-sight-a", "cat-sight-b"],
                            "cat-silencer",
                        ],
                        "attributes": [
                            {
                                "name": "ergonomics",
                                "requirement": {
                                    "compareMethod": ">=",
                                    "value": 45,
                                },
                            }
                        ],
                    }
                ],
            }
        },
        "locale": {
            "gun1 Name": "测试步枪",
            "grip1 Name": "握把甲",
            "cat-sight-a Name": "红点瞄具",
            "cat-sight-b Name": "全息瞄具",
            "cat-silencer Name": "消音器",
        },
    }
    rows = gs.collect_gunsmith_tasks(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"] == "gs"
    assert row["objective_id"] == "o-b"
    assert row["weapon_id"] == "gun1"
    assert row["faction_name"] == "Any"
    assert row["constraints"]["min_ergonomics"] == 45
    assert row["required_items"][0]["id"] == "grip1"
    groups = row["required_category_groups"]
    assert {item["id"] for item in groups[0]} == {"cat-sight-a", "cat-sight-b"}
    assert {item["name"] for item in groups[0]} == {"红点瞄具", "全息瞄具"}
    assert groups[1][0]["id"] == "cat-silencer"
    assert groups[1][0]["name"] == "消音器"
    assert row["required_items"][0]["name"] == "握把甲"


def test_collect_gunsmith_tasks_from_dump_build_attributes():
    payload = {
        "tasks": {
            "gs": {
                "id": "gs",
                "name": "Gunsmith - AK-105",
                "trader": PRAPOR,
                "objectives": [
                    {
                        "id": "o-b",
                        "type": "buildWeapon",
                        "item": "gun1",
                        "containsAll": [],
                        "containsCategory": ["cat-silencer"],
                        "buildAttributes": {
                            "accuracy": {"value": 0, "compareMethod": ">="},
                            "durability": {"value": 60, "compareMethod": ">="},
                            "effectiveDistance": {"value": 800, "compareMethod": ">="},
                            "ergonomics": {"value": 21, "compareMethod": ">="},
                            "height": {"value": 2, "compareMethod": ">="},
                            "magazineCapacity": {"value": 60, "compareMethod": ">="},
                            "muzzleVelocity": {"value": 0, "compareMethod": ">="},
                            "recoil": {"value": 500, "compareMethod": "<="},
                            "weight": {"value": 4.8, "compareMethod": "<="},
                            "width": {"value": 4, "compareMethod": ">="},
                        },
                    }
                ],
            }
        },
        "locale": {
            "gun1 Name": "AK-105",
            "cat-silencer Name": "消音器",
        },
    }
    rows = gs.collect_gunsmith_tasks(payload)
    assert len(rows) == 1
    constraints = rows[0]["constraints"]
    assert constraints["min_ergonomics"] == 21
    assert constraints["max_recoil_sum"] == 500
    assert constraints["max_weight"] == 4.8
    assert constraints["min_mag_capacity"] == 60
    assert constraints["min_sighting_range"] == 800
    assert constraints["min_durability"] == 60
    assert "min_width" not in constraints
    assert "min_height" not in constraints
    assert "min_accuracy" not in constraints


def test_fill_gunsmith_names_from_index():
    index = wb.build_index("json.tarkov.dev", _payload())
    rows = [
        {
            "required_items": [{"id": "grip1", "name": "grip1"}],
            "required_category_groups": [],
        }
    ]
    gs._fill_gunsmith_display_names(None, rows, index)
    assert rows[0]["required_items"][0]["name"] == "握把甲"


def test_lookup_category_names_from_items_dump():
    from app.services.tarkov import catalog as catalog

    cat_id = "59ba36404bdc2d1c198b456c"
    names = catalog.lookup_category_names(
        {
            "itemCategories": {cat_id: {"normalizedName": "silencer"}},
            "locale": {f"{cat_id} Name": "消音器"},
        },
        {cat_id},
    )
    assert names[cat_id] == "消音器"


def test_evaluate_and_solve_required_item():
    index = wb.build_index("json.tarkov.dev", _payload())
    gun = index.items["gun1"]
    spec = {
        "required_items": [{"id": "grip2", "name": "握把乙"}],
        "required_category_groups": [],
        "constraints": {"min_ergonomics": 40},
    }
    factory = wb._pairs_map(wb.map_factory_pairs(index, "gun1"))
    before = gs.evaluate_build(index, gun, factory, spec)
    assert before["missing_items"][0]["id"] == "grip2"
    result = gs.solve_spec(index, gun, spec)
    assert result["status"] == "optimal"
    installed = {slot: item for slot, item in result["pairs"]}
    assert installed.get("slot-grip") == "grip2"
    assert result["checklist"]["ok"] is True


def test_evaluate_skips_durability_and_flags_max_mag():
    index = wb.build_index("json.tarkov.dev", _payload())
    gun = index.items["gun1"]
    factory = wb._pairs_map(wb.map_factory_pairs(index, "gun1"))
    check = gs.evaluate_build(
        index,
        gun,
        factory,
        {
            "required_items": [],
            "required_category_groups": [],
            "constraints": {
                "min_durability": 60,
                "max_width": 3,
                "max_mag_capacity": 5,
            },
        },
    )
    assert "min_durability" not in check["unmet_constraints"]
    assert "max_width" not in check["unmet_constraints"]
    assert "max_mag_capacity" in check["unmet_constraints"]
