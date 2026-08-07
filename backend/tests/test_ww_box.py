"""鸣潮 roleBox：字符串 data 解包与 parse。"""

from __future__ import annotations

import json

from app.services.kujiequ_boxes import parse_ww_box, unwrap_aki_data
from app.services.kujiequ_client import GameRole


def _role() -> GameRole:
    return GameRole(
        game_id=3,
        game_name="鸣潮",
        role_id="101812955",
        role_name="首席",
        server_id="76402e5b20be2c39f095a152090afddc",
        server_name="鸣潮",
        user_id="10065669",
    )


def test_unwrap_aki_data_string_payload():
    inner = {
        "name": "首席",
        "id": 101812955,
        "level": 40,
        "worldLevel": 5,
        "roleNum": 16,
        "energy": 206,
        "maxEnergy": 240,
    }
    envelope = {
        "code": 200,
        "msg": "请求成功",
        "data": json.dumps(inner, ensure_ascii=False),
        "success": True,
    }
    assert unwrap_aki_data(envelope)["level"] == 40
    assert unwrap_aki_data(envelope)["name"] == "首席"


def test_unwrap_aki_data_already_dict():
    envelope = {"code": 200, "data": {"level": 12, "name": "测"}}
    assert unwrap_aki_data(envelope)["level"] == 12


def test_parse_ww_box_base_and_calabash():
    raw = {
        "base": {
            "name": "首席",
            "id": 101812955,
            "level": 40,
            "worldLevel": 5,
            "activeDays": 28,
            "roleNum": 16,
            "achievementCount": 67,
            "achievementStar": 120,
            "energy": 206,
            "maxEnergy": 240,
            "storeEnergy": 100,
            "storeEnergyLimit": 480,
            "storeEnergyTitle": "结晶单质",
            "storeEnergyIconUrl": "https://example.com/store.png",
            "liveness": 80,
            "livenessMaxCount": 100,
            "smallCount": 60,
            "bigCount": 10,
            "soundBox": 7,
            "weeklyInstCount": 1,
            "weeklyInstCountLimit": 3,
            "weeklyInstTitle": "战歌重奏收取次数",
            "rougeScore": 1200,
            "rougeScoreLimit": 6000,
            "rougeTitle": "千道门扉的异想",
            "treasureBoxList": [
                {"name": "朴素奇藏箱", "num": 10},
                {"name": "辉光奇藏箱", "num": 2},
            ],
            "phantomBoxList": [
                {"name": "潮汐之遗·绿", "num": 3},
            ],
            "boxList": [
                {"boxName": "朴素奇藏箱", "num": 99},
            ],
        },
        "calabash": {
            "level": 16,
            "unlockCount": 170,
            "maxCount": 208,
            "cost": 12,
        },
    }
    box = parse_ww_box(raw, role=_role())
    assert box.uid == "101812955"
    assert box.role_name == "首席"
    assert box.level == 40
    assert box.world_level == 5
    assert box.active_days == 28
    assert box.role_num == 16
    assert box.achievement_count == 67
    assert box.energy == 206
    assert box.max_energy == 240
    assert box.store_energy == 100
    assert box.liveness == 80
    assert box.rouge_score == 1200
    assert box.calabash_level == 16
    assert box.calabash_unlock == 170
    assert box.calabash_max == 208
    assert [t.name for t in box.treasure_boxes] == ["朴素奇藏箱", "辉光奇藏箱"]
    assert box.treasure_boxes[0].num == 10
    assert box.phantom_boxes[0].name == "潮汐之遗·绿"


def test_parse_ww_box_prefers_treasure_over_box_list():
    """有 treasureBoxList 时不回退到 boxList。"""
    raw = {
        "base": {
            "treasureBoxList": [{"name": "A", "num": 1}],
            "boxList": [{"boxName": "B", "num": 9}],
        },
        "calabash": {},
    }
    box = parse_ww_box(raw, role=_role())
    assert len(box.treasure_boxes) == 1
    assert box.treasure_boxes[0].name == "A"


def test_parse_ww_box_fallback_box_list():
    raw = {
        "base": {
            "boxList": [{"boxName": "基准奇藏箱", "num": 29}],
        },
        "calabash": {},
    }
    box = parse_ww_box(raw, role=_role())
    assert box.treasure_boxes[0].name == "基准奇藏箱"
    assert box.treasure_boxes[0].num == 29


def test_rolebox_headers_omit_user_token_for_data_apis():
    from app.services.kujiequ_boxes import _rolebox_headers
    from app.services.kujiequ_client import KujiequCredentials

    creds = KujiequCredentials(
        token="user-jwt-token",
        dev_code="ABCDEF1234567890ABCDEF1234567890",
        distinct_id="11111111-2222-3333-4444-555555555555",
    )
    data_headers = _rolebox_headers(creds, bat="bat-token", with_user_token=False)
    assert "token" not in data_headers
    assert "Cookie" not in data_headers
    assert data_headers["did"] == creds.dev_code
    assert data_headers["b-at"] == "bat-token"

    auth_headers = _rolebox_headers(creds, bat="", with_user_token=True)
    assert auth_headers["token"] == "user-jwt-token"
    assert auth_headers["did"] == creds.dev_code
    assert auth_headers["b-at"] == ""
