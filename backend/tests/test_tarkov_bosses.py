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


def test_parse_boss_rows_from_json_dump():
    env = _envelope()
    dump = {
        "data": {"maps": env["maps"], "mobs": env["mobs"]},
        "locale": env.get("locale") or {},
    }
    dump_rows = bosses.parse_boss_rows(dump)
    env_rows = bosses.parse_boss_rows(env)
    assert dump_rows
    assert [r["slug"] for r in dump_rows] == [r["slug"] for r in env_rows]
    killa = next(r for r in dump_rows if r["slug"] == "killa")
    assert killa["kind"] == "boss"
    assert killa["health_total"] == 890
    assert "立交桥" in killa["maps_label"]


def test_parse_killa_maps_health_and_behavior():
    rows = bosses.parse_boss_rows(_envelope())
    by_slug = {r["slug"]: r for r in rows}
    killa = by_slug["killa"]
    assert killa["name"] == "Killa"
    assert "nickname" not in killa
    assert killa["behavior_zh"] == "巡逻，重装甲"
    assert killa["health_total"] == 890
    assert killa["health"][0]["name"] == "胸腔"
    assert "立交桥" in killa["maps_label"]
    assert "码头" in killa["maps_label"]
    assert "45%（立交桥）" in killa["spawn_label"]
    assert "20%（码头）" in killa["spawn_label"]
    assert killa["description"].startswith("塔科夫的终极猛男")


def test_parse_goons_escorts():
    rows = bosses.parse_boss_rows(_envelope())
    knight = next(r for r in rows if r["slug"] == "knight")
    assert "nickname" not in knight
    slugs = {e["slug"] for e in knight["escorts"]}
    assert slugs == {"big-pipe", "birdeye"}
    assert all("nickname" not in e for e in knight["escorts"])
    assert knight["escorts_label"] == "×2"
    by_id = {r["id"]: r for r in rows}
    pipe = by_id["followerBigPipe"]
    bird = by_id["followerBirdEye"]
    assert pipe["parent_ids"] == ["bossKnight"]
    assert bird["parent_ids"] == ["bossKnight"]
    assert "海关" in pipe["maps_label"]
    assert "海关" in bird["maps_label"]
    assert by_id["bossKnight"]["parent_ids"] == []


def test_land_label_covers_raid_overflow():
    assert bosses.land_label(-1) == "开局"
    assert bosses.land_label(-1, random=True) == "开局"
    assert bosses.land_label(900) == "15分钟"
    assert bosses.land_label(5790, raid_duration=50) == "与战局时间无关"
    assert bosses.land_label(9999) == "与战局时间无关"
    assert bosses.land_label(-1, trigger="Switch") == "触发后落地"


def test_spawn_groups_merge_maps_and_split_on_land():
    payload = {
        "maps": {
            "customs": {
                "id": "customs",
                "normalizedName": "customs",
                "name": "Customs",
                "raidDuration": 45,
                "bosses": [
                    {
                        "mob": "bossKnight",
                        "spawnChance": 0.2,
                        "spawnTime": -1,
                        "spawnTimeRandom": True,
                        "spawnLocations": [
                            {
                                "name": "Dorms",
                                "chance": 1,
                                "positions": [{"x": 10, "y": 2, "z": 30}],
                            }
                        ],
                        "escorts": [
                            {
                                "mob": "followerBigPipe",
                                "amount": [{"chance": 1, "count": 1}],
                            }
                        ],
                    }
                ],
            },
            "woods": {
                "id": "woods",
                "normalizedName": "woods",
                "name": "Woods",
                "raidDuration": 40,
                "bosses": [
                    {
                        "mob": "bossKnight",
                        "spawnChance": 0.2,
                        "spawnTime": -1,
                        "spawnTimeRandom": True,
                        "spawnLocations": [{"name": "Sawmill", "chance": 1}],
                        "escorts": [
                            {
                                "mob": "followerBigPipe",
                                "amount": [{"chance": 1, "count": 1}],
                            }
                        ],
                    }
                ],
            },
            "icebreaker": {
                "id": "icebreaker",
                "normalizedName": "icebreaker",
                "name": "Icebreaker",
                "raidDuration": 40,
                "bosses": [
                    {
                        "mob": "bossKnight",
                        "spawnChance": 1,
                        "spawnTime": 9999,
                        "spawnTimeRandom": False,
                        "spawnLocations": [{"name": "Deck", "chance": 1}],
                        "escorts": [
                            {
                                "mob": "ExUsec",
                                "amount": [{"chance": 1, "count": 2}],
                            }
                        ],
                    }
                ],
            },
        },
        "mobs": {
            "bossKnight": {
                "id": "bossKnight",
                "name": "bossKnight",
                "normalizedName": "knight",
                "health": [],
            },
            "followerBigPipe": {
                "id": "followerBigPipe",
                "name": "followerBigPipe",
                "normalizedName": "big-pipe",
                "health": [],
            },
            "ExUsec": {
                "id": "ExUsec",
                "name": "ExUsec",
                "normalizedName": "rogue",
                "health": [],
            },
        },
        "locale": {
            "customs Name": "海关",
            "woods Name": "森林",
            "icebreaker Name": "破冰船",
            "bossKnight Name": "Knight",
            "followerBigPipe Name": "Big Pipe",
            "ExUsec Name": "游荡者",
        },
    }
    knight = next(r for r in bosses.parse_boss_rows(payload) if r["slug"] == "knight")
    groups = knight["spawn_groups"]
    assert [g["land_label"] for g in groups] == ["开局", "与战局时间无关"]
    assert [m["name"] for m in groups[0]["maps"]] == ["海关", "森林"]
    assert groups[0]["shared_spawn_chance"] == "20%"
    assert groups[0]["locations"][0]["positions"] == [{"x": 10.0, "y": 2.0, "z": 30.0}]
    assert groups[0]["escorts"][0]["slug"] == "big-pipe"
    assert groups[1]["escorts"][0]["count"] == 2
    assert groups[1]["shared_spawn_chance"] == "100%"


def test_aliases():
    assert bosses.resolve_boss_slug("goons") == "knight"
    assert bosses.resolve_boss_slug("cultists") == "cultist-priest"
    assert bosses.resolve_boss_slug("Killa") == "killa"
    assert bosses.resolve_boss_slug("bear") == "vs-rf"
    assert bosses.resolve_boss_slug("usec") == "vs-rf-sniper"


def test_classify_boss_kind_splits_soldiers_and_elites():
    assert bosses.classify_boss_kind("bossKilla", "killa") == "boss"
    assert bosses.classify_boss_kind("blackDivision", "black-div") == "boss"
    assert bosses.classify_boss_kind("PmcBot", "raider") == "elite"
    assert bosses.classify_boss_kind("exUsec", "rogue") == "elite"
    assert bosses.classify_boss_kind("sectantPriest", "cultist-priest") == "elite"
    assert bosses.classify_boss_kind("vsRF", "vs-rf") == "soldier"
    assert bosses.classify_boss_kind("vsRFSniper", "vs-rf-sniper") == "soldier"
    assert bosses.classify_boss_kind("Sentry", "sentry") == "soldier"
    assert bosses.classify_boss_kind("pmcBEAR", "bear") == "soldier"
    assert bosses.classify_boss_kind("pmcUSEC", "usec") == "soldier"


def test_generic_normalized_name_uses_mob_id_slug():
    payload = {
        "maps": {
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
                    }
                ],
            }
        },
        "mobs": {
            "vsRF": {
                "id": "vsRF",
                "name": "vsRF",
                "normalizedName": "af",
                "health": [],
                "items": [],
                "equipment": [],
            }
        },
    }
    rows = bosses.parse_boss_rows(payload)
    assert len(rows) == 1
    assert rows[0]["slug"] == "vs-rf"
    assert rows[0]["kind"] == "soldier"
    assert rows[0]["name"] == "俄军"


def test_generic_norm_escorts_use_assigned_slug():
    payload = {
        "maps": {
            "terminal": {
                "id": "terminal",
                "name": "Terminal",
                "normalizedName": "terminal",
                "bosses": [
                    {
                        "mob": "vsRF",
                        "spawnChance": 1,
                        "spawnLocations": [],
                        "escorts": [
                            {
                                "mob": "vsRF",
                                "amount": [{"chance": 1, "count": 1}],
                            }
                        ],
                    }
                ],
            }
        },
        "mobs": {
            "vsRF": {
                "id": "vsRF",
                "name": "vsRF",
                "normalizedName": "af",
                "health": [],
                "items": [],
                "equipment": [],
            }
        },
        "locale": {"vsRF": "俄军"},
    }
    rows = bosses.parse_boss_rows(payload)
    assert len(rows) == 1
    escorts = rows[0]["escorts"]
    assert escorts[0]["slug"] == "vs-rf"
    assert escorts[0]["name"] == "俄军"
    group = rows[0]["spawn_groups"][0]
    assert group["escorts"][0]["slug"] == "vs-rf"


def test_pve_pmc_bear_is_not_the_terminal_vsrf():
    payload = {
        "maps": {
            "customs": {
                "id": "customs",
                "name": "Customs",
                "normalizedName": "customs",
                "bosses": [
                    {
                        "mob": "pmcBEAR",
                        "spawnChance": 0.5,
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
                    }
                ],
            },
        },
        "mobs": {
            "pmcBEAR": {
                "id": "pmcBEAR",
                "name": "pmcBEAR",
                "normalizedName": "bear",
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
        },
        "locale": {"pmcBEAR": "BEAR", "vsRF": "俄军"},
    }
    rows = bosses.parse_boss_rows(payload)
    by_id = {r["id"]: r for r in rows}
    assert by_id["pmcBEAR"]["slug"] == "bear"
    assert by_id["pmcBEAR"]["kind"] == "soldier"
    assert by_id["pmcBEAR"]["name"] == "BEAR"
    assert by_id["vsRF"]["slug"] == "vs-rf"
    assert by_id["vsRF"]["kind"] == "soldier"
    assert by_id["vsRF"]["name"] == "俄军"
    names = [r["name"] for r in rows]
    assert names.count("BEAR") == 1
    assert bosses._find_boss_row(rows, "bear")["id"] == "pmcBEAR"
    assert bosses._find_boss_row(rows, "vs-rf")["id"] == "vsRF"


def test_copy_missing_map_locks_keeps_old_doors():
    new_maps = {
        "customs": {"normalizedName": "customs", "bosses": []},
        "lab": {"normalizedName": "the-lab", "accessKeys": ["lab-card"]},
    }
    old_maps = {
        "customs": {
            "normalizedName": "customs",
            "locks": [{"key": "dorm-114"}],
        },
        "other": {
            "normalizedName": "the-lab",
            "accessKeys": ["old-card"],
        },
    }
    assert bosses.copy_missing_map_locks(new_maps, old_maps) == 1
    assert new_maps["customs"]["locks"] == [{"key": "dorm-114"}]
    assert new_maps["lab"]["accessKeys"] == ["lab-card"]


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
    assert by_id["Sentry"]["kind"] == "soldier"
    assert by_id["Sentry"]["name"] == "守军"
    assert by_id["vsRF"]["slug"] == "vs-rf"
    assert by_id["vsRF"]["kind"] == "soldier"
    assert by_id["vsRF"]["name"] == "俄军"
    assert by_id["vsRFSniper"]["slug"] == "vs-rf-sniper"
    assert by_id["vsRFSniper"]["kind"] == "soldier"
    assert by_id["vsRFSniper"]["name"] == "俄军狙击"
    assert by_id["PmcBot"]["slug"] == "raider"
    assert by_id["PmcBot"]["kind"] == "elite"
    assert by_id["PmcBot"]["name"] == "掠夺者"
    assert by_id["blackDivision"]["slug"] == "black-div"
    assert by_id["blackDivision"]["kind"] == "boss"
    assert by_id["blackDivision"]["name"] == "黑色军团"
    assert [r["kind"] for r in rows] == ["boss", "elite", "soldier", "soldier", "soldier"]
    assert by_id["Sentry"]["maps_label"] == "海岸线"
    assert "码头" in by_id["vsRF"]["maps_label"]
    assert "实验室" in by_id["PmcBot"]["maps_label"]


def test_armor_class_reads_plate_properties():
    assert bosses._armor_class({"properties": {"class": 4}}) == 4
    assert bosses._armor_class({"properties": {"armorClass": 6}}) == 6
    assert bosses._armor_class({"properties": {"class": 0}}) is None
    assert bosses._armor_class({}) is None


def test_contains_entries_accepts_legacy_ids_and_dump_objects():
    assert bosses._contains_entries(["ammo-1", {"item": "ammo-2", "count": 30}]) == [
        {"item": "ammo-1", "count": 1},
        {"item": "ammo-2", "count": 30},
    ]
    slim = bosses._slim_equipment(
        [
            {
                "item": "gun-1",
                "count": 1,
                "containsItems": [{"item": "ammo-2", "quantity": 60}],
            }
        ]
    )
    assert slim == [
        {
            "item": "gun-1",
            "count": 1,
            "contains": [{"item": "ammo-2", "count": 60}],
        }
    ]
    with_slot = bosses._slim_equipment(
        [
            {
                "item": "korund",
                "attributes": {"slot": "ArmorVest"},
            },
            {
                "item": "plate",
                "attributes": {"slot": "Front_plate"},
            },
        ]
    )
    assert with_slot == [
        {"item": "korund", "count": 1, "contains": [], "slot": "ArmorVest"},
        {"item": "plate", "count": 1, "contains": [], "slot": "Front_plate"},
    ]


def test_equipment_slot_prefers_handbook_then_types():
    assert bosses.equipment_slot_for_item({"types": ["helmet"]}) == (
        "headwear",
        "头部装备",
    )
    assert bosses.equipment_slot_for_item({"types": ["armor", "rig"]}) == (
        "armor",
        "身体护甲",
    )
    assert bosses.equipment_slot_for_item({"types": ["armorPlate"]}) == (
        "armor",
        "身体护甲",
    )
    assert bosses.equipment_slot_for_item(
        {
            "types": ["armorPlate"],
            "properties_type": "ItemPropertiesArmorAttachment",
        }
    ) == ("armor", "身体护甲")
    assert bosses.equipment_slot_for_item({"types": ["rig"]}) == ("rig", "战术胸挂")
    assert bosses.equipment_slot_for_item(
        {"types": ["gun"], "handbook_ids": [bosses.HB_PISTOL]}
    ) == ("pistol", "手枪")
    assert bosses.equipment_slot_for_item({"types": ["gun"]}) == ("gun", "武器")
    assert bosses.equipment_slot_for_item(
        {"handbook_ids": [bosses.HB_FACE]}
    ) == ("face", "面部装备")
    assert bosses.equipment_slot_for_item(
        {
            "types": ["glasses", "wearable"],
            "properties_type": "ItemPropertiesArmorAttachment",
        }
    ) == ("face", "面部装备")
    assert bosses.equipment_slot_for_item({"types": ["barter"]}) == (
        bosses.EQUIPMENT_SLOT_OTHER,
        bosses.EQUIPMENT_SLOT_OTHER_LABEL,
    )
    assert bosses.skip_equipment_slot_item(
        {"types": ["mods"], "properties_type": "ItemPropertiesMagazine"}
    )
    assert bosses.skip_equipment_slot_item({"types": ["ammo"]})
    assert not bosses.skip_equipment_slot_item(
        {"types": ["ammo", "grenade"], "properties_type": "ItemPropertiesGrenade"}
    )


def test_build_equipment_slots_groups_nests_and_dedupes():
    row = {
        "equipment": [
            {"item": "helm-a", "count": 1, "contains": []},
            {"item": "helm-b", "contains": []},
            {"item": "helm-a", "contains": []},
            {
                "item": "rpk",
                "contains": [
                    {"item": "grip", "count": 1},
                    {"item": "mag", "count": 1},
                    {"item": "bp", "count": 60},
                    {"item": "bp", "count": 30},
                ],
            },
            {
                "item": "rpk",
                "contains": ["bt"],
            },
            {"item": "korund", "contains": [{"item": "plate"}]},
            {"item": "plate", "contains": []},
            {"item": "mag", "contains": []},
        ]
    }
    items = {
        "helm-a": {
            "id": "helm-a",
            "name": "Altyn",
            "icon_link": "a.png",
            "types": ["helmet"],
            "handbook_ids": [bosses.HB_HEADWEAR],
        },
        "helm-b": {
            "id": "helm-b",
            "name": "Vulkan-5",
            "types": ["helmet"],
        },
        "rpk": {
            "id": "rpk",
            "name": "RPK-16",
            "types": ["gun", "preset"],
        },
        "grip": {
            "id": "grip",
            "name": "AK grip",
            "types": ["mods"],
            "properties_type": "ItemPropertiesWeaponMod",
        },
        "mag": {
            "id": "mag",
            "name": "60-round mag",
            "types": ["mods"],
            "properties_type": "ItemPropertiesMagazine",
        },
        "bp": {
            "id": "bp",
            "name": "5.45 BP",
            "types": ["ammo"],
            "properties_type": "ItemPropertiesAmmo",
            "properties": {
                "damage": 46,
                "penetrationPower": 45,
                "armorDamage": 57,
            },
        },
        "bt": {
            "id": "bt",
            "name": "5.45 BT",
            "types": ["ammo"],
        },
        "korund": {
            "id": "korund",
            "name": "Korund-VM",
            "types": ["armor", "rig"],
        },
        "plate": {
            "id": "plate",
            "name": "Granit",
            "types": ["armorPlate"],
            "properties": {"class": 5},
        },
    }
    slots = bosses.build_equipment_slots(row, items)
    by_key = {s["key"]: s for s in slots}
    assert [s["key"] for s in slots] == ["headwear", "armor", "gun"]
    assert by_key["armor"]["label"] == "身体护甲"
    assert by_key["headwear"]["label"] == "头部装备"
    assert [it["item_id"] for it in by_key["headwear"]["items"]] == ["helm-a", "helm-b"]
    gun = by_key["gun"]["items"][0]
    assert gun["name"] == "RPK-16"
    assert [c["item_id"] for c in gun["contains"]] == ["mag", "bp", "bt"]
    assert gun["contains"][0]["kind"] == "magazine"
    assert gun["contains"][1]["kind"] == "ammo"
    assert gun["contains"][1]["count"] == 60
    assert gun["contains"][1]["damage"] == 46
    assert gun["contains"][1]["penetration"] == 45
    assert gun["contains"][1]["armor_damage"] == 57
    assert gun["contains"][2]["kind"] == "ammo"
    assert gun["contains"][2]["damage"] is None
    armor = by_key["armor"]["items"][0]
    assert armor["name"] == "Korund-VM"
    assert armor["contains"][0]["item_id"] == "plate"
    assert armor["contains"][0]["kind"] == "plate"
    assert armor["contains"][0]["armor_class"] == 5
    assert [it["item_id"] for it in by_key["armor"]["items"]] == ["korund"]


def _gear_catalog() -> dict:
    return {
        "korund": {
            "id": "korund",
            "name": "Korund-VM",
            "types": ["armor"],
        },
        "avs": {
            "id": "avs",
            "name": "AVS",
            "types": ["rig"],
        },
        "front": {
            "id": "front",
            "name": "Granit Br4",
            "types": ["armorPlate"],
            "properties": {"class": 4},
        },
        "back": {
            "id": "back",
            "name": "Granit Br5",
            "types": ["armorPlate"],
            "properties": {"class": 5},
        },
        "gun": {
            "id": "gun",
            "name": "RPK",
            "types": ["gun"],
        },
    }


def test_build_equipment_slots_nests_dump_plate_slots_under_armor():
    items = _gear_catalog()
    slots = bosses.build_equipment_slots(
        {
            "equipment": [
                {
                    "item": "avs",
                    "slot": "TacticalVest",
                    "contains": [],
                },
                {"item": "gun", "slot": "FirstPrimaryWeapon", "contains": []},
                {
                    "item": "korund",
                    "slot": "ArmorVest",
                    "contains": [],
                },
                {
                    "item": "front",
                    "slot": "Front_plate",
                    "contains": [],
                },
                {
                    "item": "back",
                    "slot": "Back_plate",
                    "contains": [],
                },
            ]
        },
        items,
    )
    by_key = {s["key"]: s for s in slots}
    assert [it["item_id"] for it in by_key["armor"]["items"]] == ["korund"]
    assert [c["item_id"] for c in by_key["armor"]["items"][0]["contains"]] == [
        "front",
        "back",
    ]
    assert by_key["armor"]["items"][0]["contains"][0]["kind"] == "plate"
    assert by_key["armor"]["items"][0]["contains"][0]["armor_class"] == 4
    assert by_key["rig"]["items"][0]["contains"] == []
    assert "armorPlate" not in [s["key"] for s in slots]


def test_build_equipment_slots_nests_plates_under_tactical_vest():
    items = _gear_catalog()
    slots = bosses.build_equipment_slots(
        {
            "equipment": [
                {
                    "item": "avs",
                    "attributes": {"slot": "TacticalVest"},
                    "contains": [],
                },
                {
                    "item": "front",
                    "attributes": {"slot": "front_plate"},
                    "contains": [],
                },
            ]
        },
        items,
    )
    by_key = {s["key"]: s for s in slots}
    assert list(by_key) == ["rig"]
    assert [c["item_id"] for c in by_key["rig"]["items"][0]["contains"]] == ["front"]


def test_build_equipment_slots_keeps_orphan_plates_top_level():
    items = _gear_catalog()
    slots = bosses.build_equipment_slots(
        {
            "equipment": [
                {"item": "front", "slot": "Front_plate", "contains": []},
            ]
        },
        items,
    )
    by_key = {s["key"]: s for s in slots}
    assert [it["item_id"] for it in by_key["armor"]["items"]] == ["front"]
    assert by_key["armor"]["items"][0]["contains"] == []


def test_parse_normalizes_dump_equipment_objects():
    payload = {
        "maps": {
            "factory": {
                "id": "factory",
                "normalizedName": "factory",
                "name": "Factory",
                "bosses": [
                    {
                        "mob": "bossTagilla",
                        "spawnChance": 1,
                        "spawnLocations": [{"name": "Shop", "chance": 1}],
                        "escorts": [],
                    }
                ],
            }
        },
        "mobs": {
            "bossTagilla": {
                "id": "bossTagilla",
                "normalizedName": "tagilla",
                "equipment": [
                    {
                        "item": {"id": "helm-1"},
                        "containsItems": [{"item": {"id": "ammo-1"}, "count": 20}],
                    }
                ],
                "items": [],
                "health": [],
            }
        },
        "locale": {"bossTagilla": "Tagilla"},
    }
    tagilla = next(r for r in bosses.parse_boss_rows(payload) if r["slug"] == "tagilla")
    assert tagilla["equipment"] == [
        {
            "item": "helm-1",
            "count": 1,
            "contains": [{"item": "ammo-1", "count": 20}],
        }
    ]


def test_mob_loot_item_ids_includes_items_and_contains() -> None:
    ids = bosses.mob_loot_item_ids(
        {
            "item_ids": ["gun", {"id": "helmet"}],
            "equipment": [
                {
                    "item": "armor",
                    "contains": [{"item": "plate", "count": 1}, "extra"],
                }
            ],
        }
    )
    assert ids == {"gun", "helmet", "armor", "plate", "extra"}
    assert bosses.mob_loot_item_ids(None) == set()
