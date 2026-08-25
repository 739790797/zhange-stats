"""Unit tests for tarkov boss parse / loot / aliases."""

from __future__ import annotations

from app.services.tarkov import bosses as bosses


def _envelope() -> dict:
    return {
        "maps": {
            "interchange": {
                "id": "interchange",
                "name": "Interchange",
                "normalizedName": "interchange",
                "bosses": [
                    {
                        "mob": "bossKilla",
                        "spawnChance": 0.45,
                        "spawnLocations": [
                            {"name": "ZoneCenterBot", "chance": 0.4},
                            {"name": "ZoneOLI", "chance": 0.2},
                        ],
                        "escorts": [],
                    }
                ],
            },
            "terminal": {
                "id": "terminal",
                "name": "Terminal",
                "normalizedName": "terminal",
                "bosses": [
                    {
                        "mob": "bossKilla",
                        "spawnChance": 0.2,
                        "spawnLocations": [{"name": "Dock", "chance": 1}],
                        "escorts": [],
                    }
                ],
            },
            "customs": {
                "id": "customs",
                "name": "Customs",
                "normalizedName": "customs",
                "bosses": [
                    {
                        "mob": "bossKnight",
                        "spawnChance": 0.15,
                        "spawnLocations": [{"name": "Dorms", "chance": 1}],
                        "escorts": [
                            {
                                "mob": "followerBigPipe",
                                "amount": [{"chance": 1, "count": 1}],
                            },
                            {
                                "mob": "followerBirdEye",
                                "amount": [{"chance": 1, "count": 1}],
                            },
                        ],
                    }
                ],
            },
        },
        "mobs": {
            "bossKilla": {
                "id": "bossKilla",
                "name": "bossKilla",
                "normalizedName": "killa",
                "imagePortraitLink": "https://assets.tarkov.dev/killa-portrait.png",
                "imagePosterLink": "https://assets.tarkov.dev/killa-poster.jpg",
                "health": [
                    {
                        "id": "Chest",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/Chest",
                        "max": 210,
                    },
                    {
                        "id": "Head",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/Head",
                        "max": 80,
                    },
                    {
                        "id": "Stomach",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/Stomach",
                        "max": 140,
                    },
                    {
                        "id": "LeftArm",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/LeftArm",
                        "max": 120,
                    },
                    {
                        "id": "RightArm",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/RightArm",
                        "max": 120,
                    },
                    {
                        "id": "LeftLeg",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/LeftLeg",
                        "max": 110,
                    },
                    {
                        "id": "RightLeg",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/RightLeg",
                        "max": 110,
                    },
                ],
                "items": ["key-g3"],
                "equipment": [{"item": "cheap-gun", "contains": []}],
            },
            "bossKnight": {
                "id": "bossKnight",
                "name": "bossKnight",
                "normalizedName": "knight",
                "imagePortraitLink": "https://assets.tarkov.dev/knight-portrait.png",
                "imagePosterLink": "",
                "health": [
                    {
                        "id": "Head",
                        "bodyPart": "QuestCondition/Elimination/Kill/BodyPart/Head",
                        "max": 80,
                    }
                ],
                "items": [],
                "equipment": [],
            },
            "followerBigPipe": {
                "id": "followerBigPipe",
                "name": "followerBigPipe",
                "normalizedName": "big-pipe",
                "health": [],
                "items": [],
                "equipment": [],
            },
            "followerBirdEye": {
                "id": "followerBirdEye",
                "name": "followerBirdEye",
                "normalizedName": "birdeye",
                "health": [],
                "items": [],
                "equipment": [],
            },
        },
        "locale": {
            "bossKilla": "Killa",
            "bossKnight": "Knight",
            "followerBigPipe": "Big Pipe",
            "followerBirdEye": "Birdeye",
            "ZoneCenterBot": "Center",
            "ZoneOLI": "OLI",
            "QuestCondition/Elimination/Kill/BodyPart/Chest": "胸腔",
            "QuestCondition/Elimination/Kill/BodyPart/Head": "头部",
        },
    }


def test_parse_killa_maps_health_and_behavior():
    rows = bosses.parse_boss_rows(_envelope())
    by_slug = {r["slug"]: r for r in rows}
    killa = by_slug["killa"]
    assert killa["name"] == "Killa"
    assert killa["nickname"] == ""
    assert killa["behavior_zh"] == "巡逻，重装甲"
    assert killa["health_total"] == 890
    assert killa["health"][0]["name"] == "胸腔"
    assert "立交桥" in killa["maps_label"]
    assert "码头" in killa["maps_label"]
    assert "45%（立交桥）" in killa["spawn_label"]
    assert "20%（码头）" in killa["spawn_label"]
    assert killa["description"].startswith("塔科夫的终极猛男")


def test_parse_goons_escorts_and_nicknames():
    rows = bosses.parse_boss_rows(_envelope())
    knight = next(r for r in rows if r["slug"] == "knight")
    assert knight["nickname"] == "骑士"
    slugs = {e["slug"] for e in knight["escorts"]}
    assert slugs == {"big-pipe", "birdeye"}
    nick = {e["slug"]: e["nickname"] for e in knight["escorts"]}
    assert nick["big-pipe"] == "大管"
    assert nick["birdeye"] == "鸟眼"
    assert knight["escorts_label"] == "×2"


def test_aliases():
    assert bosses.resolve_boss_slug("goons") == "knight"
    assert bosses.resolve_boss_slug("cultists") == "cultist-priest"
    assert bosses.resolve_boss_slug("Killa") == "killa"
    assert bosses.resolve_boss_slug("bear") == "vs-rf"
    assert bosses.resolve_boss_slug("usec") == "vs-rf-sniper"


def test_parse_keeps_duplicate_normalized_names():
    payload = {
        "maps": {
            "shoreline": {
                "id": "shoreline",
                "name": "Shoreline",
                "normalizedName": "shoreline",
                "bosses": [
                    {
                        "mob": "Sentry",
                        "spawnChance": 1,
                        "spawnLocations": [],
                        "escorts": [],
                    }
                ],
            },
            "terminal": {
                "id": "terminal",
                "name": "Terminal",
                "normalizedName": "terminal",
                "bosses": [
                    {
                        "mob": "vsRF",
                        "spawnChance": 1,
                        "spawnLocations": [],
                        "escorts": [],
                    },
                    {
                        "mob": "vsRFSniper",
                        "spawnChance": 1,
                        "spawnLocations": [],
                        "escorts": [],
                    },
                    {
                        "mob": "blackDivision",
                        "spawnChance": 1,
                        "spawnLocations": [],
                        "escorts": [],
                    },
                ],
            },
            "the-lab": {
                "id": "the-lab",
                "name": "The Lab",
                "normalizedName": "the-lab",
                "bosses": [
                    {
                        "mob": "PmcBot",
                        "spawnChance": 1,
                        "spawnLocations": [],
                        "escorts": [],
                    }
                ],
            },
        },
        "mobs": {
            "Sentry": {
                "id": "Sentry",
                "name": "Sentry",
                "normalizedName": "af",
                "health": [],
                "items": [],
                "equipment": [],
            },
            "vsRF": {
                "id": "vsRF",
                "name": "vsRF",
                "normalizedName": "af",
                "health": [],
                "items": [],
                "equipment": [],
            },
            "vsRFSniper": {
                "id": "vsRFSniper",
                "name": "vsRFSniper",
                "normalizedName": "af",
                "health": [],
                "items": [],
                "equipment": [],
            },
            "blackDivision": {
                "id": "blackDivision",
                "name": "blackDivision",
                "normalizedName": "black-div",
                "health": [],
                "items": [],
                "equipment": [],
            },
            "PmcBot": {
                "id": "PmcBot",
                "name": "PmcBot",
                "normalizedName": "raider",
                "health": [],
                "items": [],
                "equipment": [],
            },
        },
        "locale": {
            "Sentry": "守军",
            "vsRF": "俄军",
            "vsRFSniper": "俄军",
            "blackDivision": "黑色军团",
            "PmcBot": "掠夺者",
        },
    }
    rows = bosses.parse_boss_rows(payload)
    assert len(rows) == 5
    by_id = {r["id"]: r for r in rows}
    assert by_id["Sentry"]["slug"] == "sentry"
    assert by_id["Sentry"]["name"] == "守军"
    assert by_id["vsRF"]["slug"] == "vs-rf"
    assert by_id["vsRF"]["name"] == "BEAR"
    assert by_id["vsRFSniper"]["slug"] == "vs-rf-sniper"
    assert by_id["vsRFSniper"]["name"] == "USEC"
    assert by_id["PmcBot"]["slug"] == "raider"
    assert by_id["PmcBot"]["name"] == "掠夺者"
    assert by_id["blackDivision"]["slug"] == "black-div"
    assert by_id["blackDivision"]["name"] == "黑色军团"
    assert by_id["Sentry"]["maps_label"] == "海岸线"
    assert "码头" in by_id["vsRF"]["maps_label"]
    assert "实验室" in by_id["PmcBot"]["maps_label"]


def test_unique_loot_keeps_expensive_and_noflea():
    row = {
        "item_ids": ["cheap", "key-g3", "noflea-item"],
        "equipment": [{"item": "cheap-gun", "contains": []}],
    }
    items = {
        "cheap": {
            "id": "cheap",
            "name": "绷带",
            "types": ["meds"],
            "avg24h_price": 1000,
            "last_low_price": 900,
            "width": 1,
            "height": 1,
            "sell_to_trader": [],
        },
        "key-g3": {
            "id": "key-g3",
            "name": "G-3 舱室钥匙卡",
            "normalized_name": "g3-cabin-keycard",
            "types": ["keys"],
            "avg24h_price": 29_878_900,
            "last_low_price": 29_878_900,
            "width": 1,
            "height": 1,
            "sell_to_trader": [
                {
                    "slug": "therapist",
                    "name": "Therapist",
                    "price_rub": 51000,
                    "currency": "RUB",
                }
            ],
        },
        "noflea-item": {
            "id": "noflea-item",
            "name": "任务物品",
            "types": ["noFlea"],
            "avg24h_price": None,
            "last_low_price": None,
            "width": 1,
            "height": 1,
            "sell_to_trader": [],
        },
        "cheap-gun": {
            "id": "cheap-gun",
            "name": "手枪",
            "types": ["gun"],
            "avg24h_price": 20000,
            "last_low_price": 18000,
            "width": 2,
            "height": 1,
            "sell_to_trader": [],
        },
    }
    loot = bosses.build_unique_loot(row, items)
    ids = [x["item_id"] for x in loot]
    assert "cheap" not in ids
    assert "cheap-gun" not in ids
    assert "noflea-item" in ids
    key = next(x for x in loot if x["item_id"] == "key-g3")
    assert key["flea_price"] == 29_878_900
    assert key["trader_slug"] == "therapist"
    assert key["trader_price"] == 51000
    noflea = next(x for x in loot if x["item_id"] == "noflea-item")
    assert noflea["flea_price"] is None
