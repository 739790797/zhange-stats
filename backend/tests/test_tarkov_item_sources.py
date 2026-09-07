"""物品来源：items dump 无来源字段，从 barters/crafts/tasks 反查。"""

from __future__ import annotations

from app.services.tarkov.guides import parse_barters, parse_crafts, parse_hideout_stations
from app.services.tarkov.item_sources import (
    QUEST_KIND_FINISH,
    QUEST_KIND_START,
    attach_item_sources,
    collect_item_drops,
    collect_item_sources,
    collect_item_uses,
    empty_item_sources,
    empty_item_uses,
)
from app.services.tarkov.tasks import TRADER_BY_ID

PRAPOR = next(tid for tid, (slug, _name) in TRADER_BY_ID.items() if slug == "prapor")
STATION_ID = "station-workbench"


def _guides_payload() -> dict:
    return {
        "hideout": {
            STATION_ID: {
                "id": STATION_ID,
                "name": "hideout_workbench",
                "normalizedName": "workbench",
                "levels": [
                    {
                        "id": "lv1",
                        "level": 1,
                        "itemRequirements": [{"item": "bolt", "count": 4}],
                    }
                ],
            }
        },
        "locale": {"hideout_workbench": "工作台"},
        "barters": [
            {
                "id": "b1",
                "trader": PRAPOR,
                "minTraderLevel": 2,
                "taskUnlock": "task-1",
                "requiredItems": [{"item": "bolt", "count": 3}],
                "offeredItem": {"item": "target", "count": 1},
            },
            {
                "id": "b-other",
                "trader": PRAPOR,
                "minTraderLevel": 1,
                "requiredItems": [{"item": "target", "count": 1}],
                "offeredItem": {"item": "other", "count": 1},
            },
        ],
        "crafts": [
            {
                "id": "c1",
                "station": STATION_ID,
                "level": 1,
                "duration": 120,
                "requiredItems": [{"item": "bolt", "count": 2}],
                "productItem": {"item": "target", "count": 1},
            },
            {
                "id": "c-other",
                "station": STATION_ID,
                "level": 2,
                "duration": 10,
                "requiredItems": [{"item": "target", "count": 1}],
                "productItem": {"item": "other", "count": 1},
            },
        ],
    }


def _task_rows() -> list[dict]:
    return [
        {
            "id": "t-finish",
            "name": "t-finish Name",
            "normalizedName": "debut",
            "trader": PRAPOR,
            "startRewards": {"items": []},
            "finishRewards": {"items": [{"item": "target", "count": 2}]},
        },
        {
            "id": "t-start",
            "name": "Starting Out",
            "trader": PRAPOR,
            "startRewards": {"items": [{"item": "target", "count": 1}]},
            "finishRewards": {"items": [{"item": "other", "count": 1}]},
        },
        {
            "id": "t-nested",
            "name": "Pack Drop",
            "trader": PRAPOR,
            "finishRewards": {
                "items": [
                    {
                        "item": "pack",
                        "count": 1,
                        "contains": [{"item": "target", "count": 4}],
                    }
                ]
            },
        },
        {
            "id": "t-miss",
            "name": "Unrelated",
            "trader": PRAPOR,
            "finishRewards": {"items": [{"item": "other", "count": 9}]},
        },
        {
            "id": "t-use",
            "name": "Find Bolts",
            "trader": PRAPOR,
            "objectives": [
                {
                    "id": "o1",
                    "description": "上交螺栓",
                    "item": "bolt",
                    "count": 8,
                }
            ],
            "neededKeys": [{"map": "factory", "keys": ["target"]}],
        },
        {
            "id": "t-wear",
            "name": "Wear It",
            "trader": PRAPOR,
            "objectives": [
                {"id": "o2", "description": "穿上目标", "wearing": [[{"id": "target"}]]}
            ],
        },
    ]


def test_collect_item_sources_from_barter_craft_and_quest() -> None:
    payload = _guides_payload()
    sources = collect_item_sources(
        "target",
        barters=parse_barters(payload),
        crafts=parse_crafts(payload),
        tasks=_task_rows(),
        locale={"t-finish Name": "首秀"},
    )
    assert [row["id"] for row in sources["barters"]] == ["b1"]
    assert sources["barters"][0]["required_items"][0]["id"] == "bolt"
    assert [row["id"] for row in sources["crafts"]] == ["c1"]
    assert sources["crafts"][0]["station_slug"] == "workbench"
    kinds = {(row["id"], row["kind"], row["count"]) for row in sources["quest_rewards"]}
    assert kinds == {
        ("t-finish", QUEST_KIND_FINISH, 2),
        ("t-start", QUEST_KIND_START, 1),
        ("t-nested", QUEST_KIND_FINISH, 4),
    }
    finish = next(row for row in sources["quest_rewards"] if row["id"] == "t-finish")
    assert finish["name"] == "首秀"
    assert finish["trader_slug"] == "prapor"


def test_collect_item_sources_ignores_requirement_side() -> None:
    payload = _guides_payload()
    sources = collect_item_sources(
        "bolt",
        barters=parse_barters(payload),
        crafts=parse_crafts(payload),
        tasks=_task_rows(),
    )
    assert sources["barters"] == []
    assert sources["crafts"] == []
    assert sources["quest_rewards"] == []


def test_collect_item_sources_empty_id() -> None:
    assert collect_item_sources("") == empty_item_sources()


def test_collect_item_uses_from_requirement_hideout_and_tasks() -> None:
    payload = _guides_payload()
    uses = collect_item_uses(
        "bolt",
        barters=parse_barters(payload),
        crafts=parse_crafts(payload),
        stations=parse_hideout_stations(payload),
        tasks=_task_rows(),
    )
    assert [row["id"] for row in uses["barters"]] == ["b1"]
    assert [row["id"] for row in uses["crafts"]] == ["c1"]
    assert uses["hideout"] == [
        {
            "station_id": STATION_ID,
            "station_slug": "workbench",
            "station_name": "工作台",
            "level": 1,
            "count": 4,
        }
    ]
    assert uses["tasks"][0]["id"] == "t-use"
    assert uses["tasks"][0]["count"] == 8
    assert uses["tasks"][0]["notes"] == ["上交螺栓"]


def test_collect_item_uses_needed_keys_and_wearing() -> None:
    payload = _guides_payload()
    uses = collect_item_uses(
        "target",
        barters=parse_barters(payload),
        crafts=parse_crafts(payload),
        stations=parse_hideout_stations(payload),
        tasks=_task_rows(),
    )
    assert [row["id"] for row in uses["barters"]] == ["b-other"]
    assert [row["id"] for row in uses["crafts"]] == ["c-other"]
    assert uses["hideout"] == []
    assert {row["id"] for row in uses["tasks"]} == {"t-use", "t-wear"}


def test_collect_item_uses_empty_id() -> None:
    assert collect_item_uses("") == empty_item_uses()


def test_collect_item_drops_boss_and_non_boss() -> None:
    rows = [
        {
            "id": "bossKilla",
            "slug": "killa",
            "name": "Killa",
            "kind": "boss",
            "maps_label": "立交桥",
            "portrait_link": "killa.png",
            "parent_ids": [],
            "item_ids": ["target"],
            "equipment": [],
        },
        {
            "id": "pmcBot",
            "slug": "raider",
            "name": "Raider",
            "kind": "elite",
            "maps_label": "实验室",
            "portrait_link": "",
            "parent_ids": [],
            "equipment": [
                {"item": "other", "contains": [{"item": "target", "count": 1}]}
            ],
        },
        {
            "id": "assault",
            "slug": "scav",
            "name": "Scav",
            "kind": "soldier",
            "maps_label": "海关",
            "item_ids": ["other"],
            "equipment": [],
        },
        {
            "id": "bossKilla",
            "slug": "killa",
            "name": "Killa dup",
            "kind": "boss",
            "item_ids": ["target"],
            "equipment": [],
        },
    ]
    drops = collect_item_drops("target", rows)
    assert [row["slug"] for row in drops] == ["killa", "raider"]
    assert drops[0]["kind"] == "boss"
    assert drops[1]["kind"] == "elite"
    assert drops[1]["name"] == "Raider"
    assert collect_item_drops("", rows) == []
    assert collect_item_drops("target", None) == []


def test_attach_item_sources_fills_detail(monkeypatch) -> None:
    payload = _guides_payload()
    barters = parse_barters(payload)
    crafts = parse_crafts(payload)

    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_guide_rows",
        lambda db: (barters, crafts, parse_hideout_stations(payload)),
    )
    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_task_rows",
        lambda db: (_task_rows(), {"t-finish Name": "首秀"}),
    )
    monkeypatch.setattr(
        "app.services.tarkov.guides._lookup_items",
        lambda db, ids: {
            "bolt": {
                "id": "bolt",
                "name": "螺栓",
                "short_name": "bolt",
                "icon_link": "bolt.png",
                "types": ["barter"],
                "last_low_price": 1000,
                "avg24h_price": 1100,
            },
            "target": {
                "id": "target",
                "name": "目标物",
                "short_name": "tgt",
                "icon_link": "tgt.png",
                "types": ["loot"],
                "last_low_price": 5000,
                "avg24h_price": 5200,
            },
        },
    )
    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_boss_rows",
        lambda db: [
            {
                "id": "bossKilla",
                "slug": "killa",
                "name": "Killa",
                "kind": "boss",
                "maps_label": "立交桥",
                "portrait_link": "killa.png",
                "parent_ids": [],
                "item_ids": ["target"],
                "equipment": [],
            }
        ],
    )
    detail = {"id": "target"}
    attach_item_sources(object(), detail)
    assert detail["sources"]["barters"][0]["required_items"][0]["name"] == "螺栓"
    assert detail["sources"]["crafts"][0]["product_item"]["name"] == "目标物"
    assert detail["sources"]["quest_rewards"][0]["kind"] == QUEST_KIND_FINISH
    assert detail["sources"]["drops"][0]["slug"] == "killa"
    assert [row["id"] for row in detail["uses"]["barters"]] == ["b-other"]
    assert [row["id"] for row in detail["uses"]["crafts"]] == ["c-other"]


def test_attach_item_sources_swallows_errors(monkeypatch) -> None:
    def boom(_db):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_guide_rows",
        boom,
    )
    detail = {"id": "target"}
    attach_item_sources(object(), detail)
    assert detail["sources"] == empty_item_sources()
    assert detail["uses"] == empty_item_uses()


def test_attach_item_sources_keeps_trades_if_drops_fail(monkeypatch) -> None:
    payload = _guides_payload()
    barters = parse_barters(payload)
    crafts = parse_crafts(payload)

    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_guide_rows",
        lambda db: (barters, crafts, parse_hideout_stations(payload)),
    )
    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_task_rows",
        lambda db: (_task_rows(), {}),
    )
    monkeypatch.setattr(
        "app.services.tarkov.guides._lookup_items",
        lambda db, ids: {},
    )
    monkeypatch.setattr(
        "app.services.tarkov.item_sources._load_boss_rows",
        lambda db: (_ for _ in ()).throw(RuntimeError("no maps")),
    )
    detail = {"id": "target"}
    attach_item_sources(object(), detail)
    assert detail["sources"]["barters"]
    assert detail["sources"]["drops"] == []
