"""肉鸽 parse：兼容旧 dump（仅 records 摘要）与完整 RogueData。"""

from __future__ import annotations

from app.services.skland_rogue import normalize_topic_id, parse_arknights_rogue


def test_normalize_topic_id_cn_and_default():
    assert normalize_topic_id("界园") == "rogue_5"
    assert normalize_topic_id("rogue_4") == "rogue_4"
    assert normalize_topic_id("") == "rogue_5"


def test_parse_legacy_player_info_rogue_shape():
    raw = {
        "data": {
            "topics": [
                {"id": "rogue_1", "name": "傀影", "isSelected": True, "pic": ""},
                {"id": "rogue_2", "name": "水月", "isSelected": False, "pic": ""},
            ],
            "history": {
                "medal": {"count": 10, "current": 3},
                "modeGrade": 5,
                "mode": "正式",
                "score": 1200,
                "bpLevel": 20,
                "records": [
                    {
                        "id": "r1",
                        "modeGrade": 3,
                        "mode": "正式",
                        "success": 1,
                        "lastChars": [
                            {
                                "id": "char_1",
                                "name": "阿米娅",
                                "rarity": 5,
                                "profession": "CASTER",
                                "type": "",
                                "upgradePhase": 0,
                                "evolvePhase": 2,
                                "level": 80,
                                "isCandle": False,
                            }
                        ],
                        "initChars": [],
                        "troopChars": [],
                        "gainRelicList": [],
                        "cntCrossedZone": 4,
                        "cntArrivedNode": 20,
                        "cntBattleNormal": 1,
                        "cntBattleElite": 1,
                        "cntBattleBoss": 1,
                        "cntGainRelicItem": 8,
                        "cntRecruitUpgrade": 0,
                        "totemList": [],
                        "seed": "x",
                        "tagList": [{"name": "稳妥", "icon": "", "description": "", "id": 1}],
                        "lastStage": "stage",
                        "score": 900,
                        "band": {"id": "b", "name": "乐队"},
                        "startTs": "1700000000",
                        "endTs": "1700003600",
                        "endingText": "完美结局",
                        "isCollect": False,
                    }
                ],
                "favourRecords": [],
                "chars": [],
                "tagList": [],
            },
            "career": {
                "clearInfo": {"difficulty": "正式", "grade": 5, "endings": []},
                "invest": 100,
                "relic": 50,
                "game": 12,
            },
            "gameUserInfo": {"name": "博士", "level": 120, "avatar": {}, "isOfficial": True},
            "itemInfo": {},
            "userCharInfo": {},
        }
    }
    box = parse_arknights_rogue(raw, topic_id="rogue_1")
    assert box.topic_id == "rogue_1"
    assert box.overview.score == 1200
    assert box.overview.invest == 100
    assert len(box.records) == 1
    assert box.records[0].ending_text == "完美结局"
    assert box.records[0].squad[0].name == "阿米娅"
