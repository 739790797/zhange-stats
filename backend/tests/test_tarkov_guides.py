"""Unit tests for tarkov hideout / barter / craft parse."""

from __future__ import annotations

from app.services.tarkov_guides import parse_barters, parse_crafts, parse_hideout_stations
from app.services.tarkov_tasks import TRADER_BY_ID

PRAPOR = next(tid for tid, (slug, _name) in TRADER_BY_ID.items() if slug == "prapor")
STATION_ID = "station-workbench"


def _payload() -> dict:
    return {
        "hideout": {
            STATION_ID: {
                "id": STATION_ID,
                "name": "hideout_workbench",
                "normalizedName": "workbench",
                "imageLink": "https://assets.tarkov.dev/workbench.png",
                "levels": [
                    {
                        "id": "lv1",
                        "level": 1,
                        "constructionTime": 3600,
                        "description": "workbench_lv1",
                        "itemRequirements": [
                            {
                                "item": "item1",
                                "count": 2,
                                "attributes": {"foundInRaid": True},
                            }
                        ],
                        "stationLevelRequirements": [
                            {"station": "station-generator", "level": 1}
                        ],
                        "traderRequirements": [{"trader": PRAPOR, "level": 2}],
                        "skillRequirements": [{"skill": "hideout_mgmt", "level": 3}],
                    }
                ],
            },
            "station-generator": {
                "id": "station-generator",
                "name": "hideout_generator",
                "normalizedName": "generator",
                "imageLink": "",
                "levels": [
                    {
                        "id": "g1",
                        "level": 1,
                        "constructionTime": 0,
                        "itemRequirements": [{"item": "fuel", "count": 1}],
                    }
                ],
            },
        },
        "locale": {
            "hideout_workbench": "工作台",
            "hideout_generator": "发电机",
            "workbench_lv1": "解锁制作",
            "hideout_mgmt": "藏身处管理",
        },
        "barters": [
            {
                "id": "b1",
                "trader": PRAPOR,
                "minTraderLevel": 2,
                "taskUnlock": "task-1",
                "requiredItems": [{"item": "item1", "count": 3}],
                "offeredItem": {"item": "item2", "count": 1},
            },
            {
                "id": "skip",
                "trader": PRAPOR,
                "requiredItems": [{"item": "item1", "count": 1}],
                "offeredItem": {},
            },
        ],
        "crafts": [
            {
                "id": "c1",
                "station": STATION_ID,
                "level": 1,
                "duration": 120,
                "requiredItems": [{"item": "item1", "count": 1.5}],
                "productItem": {"item": "item2", "count": 1},
            }
        ],
    }


def test_parse_hideout_stations() -> None:
    rows = parse_hideout_stations(_payload())
    by_slug = {str(r["slug"]): r for r in rows}
    bench = by_slug["workbench"]
    assert bench["name"] == "工作台"
    assert bench["level_count"] == 1
    level = bench["levels"][0]
    assert level["construction_time"] == 3600
    assert level["description"] == "解锁制作"
    assert level["item_requirements"][0] == {
        "id": "item1",
        "count": 2,
        "found_in_raid": True,
    }
    assert level["trader_requirements"][0]["slug"] == "prapor"
    assert level["trader_requirements"][0]["level"] == 2
    assert level["station_requirements"][0]["station_slug"] == "generator"
    assert level["station_requirements"][0]["station_name"] == "发电机"
    assert level["skill_requirements"][0]["skill"] == "藏身处管理"


def test_parse_barters_skips_empty_offer() -> None:
    rows = parse_barters(_payload())
    assert len(rows) == 1
    row = rows[0]
    assert row["trader_slug"] == "prapor"
    assert row["min_trader_level"] == 2
    assert row["task_unlock"] == "task-1"
    assert row["offered_item"]["id"] == "item2"
    assert row["required_items"][0]["count"] == 3


def test_parse_crafts_resolves_station() -> None:
    rows = parse_crafts(_payload())
    assert len(rows) == 1
    row = rows[0]
    assert row["station_slug"] == "workbench"
    assert row["station_name"] == "工作台"
    assert row["duration"] == 120
    assert row["required_items"][0]["count"] == 1.5
    assert row["product_item"]["id"] == "item2"
