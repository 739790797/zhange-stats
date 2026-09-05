"""3×4 收集：从收集者任务抽出道具，不打真实上游。"""

from __future__ import annotations

from app.services.tarkov.collection import (
    COLLECTOR_NORMALIZED,
    apply_catalog_hits,
    extract_collection_items,
    find_collector_task_id,
    is_collector_task,
    pick_collector_raw,
)
from app.services.tarkov.tasks import project_task_detail

FENCE = "579dc571d53a0658a154fbec"


def _collector_raw() -> dict:
    return {
        "id": "collector-1",
        "name": "Collector",
        "normalizedName": "collector",
        "trader": FENCE,
        "objectives": [
            {
                "id": "o-skip",
                "type": "visit",
                "optional": False,
                "description": "go",
            },
            {
                "id": "o-opt",
                "type": "giveItem",
                "optional": True,
                "item": {"id": "opt-item", "name": "可选"},
                "foundInRaid": True,
                "count": 1,
            },
            {
                "id": "o1",
                "type": "giveItem",
                "optional": False,
                "item": {
                    "id": "item-a",
                    "name": "道具甲",
                    "iconLink": "/a.png",
                    "types": ["barter"],
                },
                "foundInRaid": True,
                "count": 1,
            },
            {
                "id": "o2",
                "type": "findItem",
                "optional": False,
                "items": [
                    {"id": "item-b", "name": "道具乙"},
                    {"id": "item-a", "name": "重复甲"},
                ],
                "foundInRaid": False,
                "count": 2,
            },
        ],
    }


def test_finds_collector_by_normalized_name() -> None:
    rows = [
        {"id": "other", "normalized_name": "debut", "name": "首秀"},
        {"id": "c1", "normalized_name": "collector", "name": "收集者"},
    ]
    assert find_collector_task_id(rows) == "c1"
    assert is_collector_task(rows[1]) is True
    assert is_collector_task(rows[0]) is False


def test_finds_collector_by_chinese_name() -> None:
    rows = [
        {"id": "c2", "normalized_name": "", "name": "收集者"},
    ]
    assert find_collector_task_id(rows) == "c2"
    raw = pick_collector_raw({"x": {"id": "x", "name": "收集者"}})
    assert raw is not None
    assert raw["id"] == "x"


def test_prefers_normalized_name_over_title() -> None:
    tasks = {
        "named": {"id": "named", "name": "收集者", "normalizedName": "other"},
        "slug": {"id": "slug", "name": "Foo", "normalizedName": "collector"},
    }
    picked = pick_collector_raw(tasks)
    assert picked is not None
    assert picked["id"] == "slug"


def test_extract_skips_optional_and_keeps_first_id() -> None:
    detail = project_task_detail(_collector_raw(), {}, include_unlocks=False)
    assert detail is not None
    items = extract_collection_items(detail)
    assert [row["id"] for row in items] == ["item-a", "item-b"]
    assert items[0]["name"] == "道具甲"
    assert items[0]["found_in_raid"] is True
    assert items[0]["objective_id"] == "o1"
    assert items[0]["types"] == ["barter"]
    assert items[0]["handbook_ids"] == []
    assert items[1]["count"] == 2
    assert items[1]["found_in_raid"] is False


def test_apply_catalog_hits_fills_size_and_short_name() -> None:
    items = [
        {
            "id": "item-a",
            "name": "道具甲",
            "short_name": "",
            "icon_link": "/a.png",
            "types": [],
            "width": 1,
            "height": 1,
            "found_in_raid": True,
            "count": 1,
            "objective_id": "o1",
        }
    ]
    apply_catalog_hits(
        items,
        {
            "item-a": {
                "name": "中文甲",
                "short_name": "甲",
                "icon_link": "/a-icon.png",
                "types": ["loot"],
                "handbook_ids": ["5b47574386f77428ca22b2ef"],
                "width": 2,
                "height": 1,
            }
        },
    )
    assert items[0]["name"] == "中文甲"
    assert items[0]["short_name"] == "甲"
    assert items[0]["icon_link"] == "/a-icon.png"
    assert items[0]["types"] == ["loot"]
    assert items[0]["handbook_ids"] == ["5b47574386f77428ca22b2ef"]
    assert items[0]["width"] == 2
    assert items[0]["height"] == 1


def test_missing_collector_returns_empty_id() -> None:
    assert find_collector_task_id([{"id": "t", "name": "首秀"}]) == ""
    assert pick_collector_raw({"t": {"id": "t", "normalizedName": "debut"}}) is None
    assert COLLECTOR_NORMALIZED == "collector"
