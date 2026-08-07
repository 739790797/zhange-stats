"""异环盒子 parse：从上游 yh/characters 整包二次加工。"""

from __future__ import annotations

from app.services.taygedo_boxes import (
    normalize_element_label,
    normalize_group_label,
    normalize_quality,
    parse_exastris_box,
    portrait_url_for,
)
from app.services.taygedo_client import TaygedoRole


def _role() -> TaygedoRole:
    return TaygedoRole(
        game_code="1289",
        game_name="异环",
        role_id="10001",
        role_name="测试角色",
    )


def test_portrait_url_for():
    assert portrait_url_for("1051").endswith("/character/tall/1051.PNG")
    assert portrait_url_for("") == ""


def test_normalize_quality_wire_enums():
    assert normalize_quality("ITEM_QUALITY_ORANGE") == "S"
    assert normalize_quality("ITEM_QUALITY_PURPLE") == "A"
    assert normalize_quality("S") == "S"
    assert normalize_quality("A") == "A"


def test_normalize_element_and_group_labels():
    assert normalize_element_label("CHARACTER_ELEMENT_TYPE_COSMOS") == "相"
    assert normalize_element_label("CHARACTER_ELEMENT_TYPE_PSYCHE") == "魂"
    assert normalize_group_label("CHARACTER_GROUP_TYPE_TWO") == "气态"
    assert normalize_group_label("CHARACTER_GROUP_TYPE_ONE") == "固态"


def test_parse_exastris_box_list_payload():
    raw = {
        "code": 0,
        "msg": "ok",
        "data": [
            {
                "id": "1051",
                "name": "早雾",
                "quality": "ITEM_QUALITY_ORANGE",
                "elementType": "CHARACTER_ELEMENT_TYPE_ANIMA",
                "groupType": "CHARACTER_GROUP_TYPE_TWO",
                "awakenLev": 2,
            },
            {
                "id": "2001",
                "name": "薄荷",
                "quality": "ITEM_QUALITY_PURPLE",
                "elementType": "CHARACTER_ELEMENT_TYPE_COSMOS",
                "groupType": "CHARACTER_GROUP_TYPE_ONE",
                "awakenLev": 0,
            },
            {
                "id": "skip",
                "name": "",
            },
        ],
    }
    box = parse_exastris_box(raw, role=_role())
    assert box.uid == "10001"
    assert box.role_name == "测试角色"
    assert box.char_count == 3
    assert box.chars[0].name == "早雾"
    assert box.chars[0].quality == "S"
    assert box.chars[0].element_type == "灵"
    assert box.chars[0].group_type == "气态"
    assert box.chars[0].awaken_lev == 2
    assert box.chars[0].portrait_url is not None
    assert "1051.PNG" in (box.chars[0].portrait_url or "")
    assert box.chars[0].element_icon_url is not None
    assert "CHARACTER_ELEMENT_TYPE_ANIMA" in (box.chars[0].element_icon_url or "")
    # S 排在 A 前
    assert [c.quality for c in box.chars[:2]] == ["S", "A"]
    assert box.chars[1].quality == "A"
    assert box.chars[1].element_type == "相"
    assert box.chars[1].group_type == "固态"


def test_parse_exastris_box_nested_list():
    raw = {
        "code": 0,
        "data": {
            "characters": [
                {"id": "1", "name": "娜娜莉", "quality": "ITEM_QUALITY_ORANGE", "awakenLev": 1},
            ]
        },
    }
    box = parse_exastris_box(raw, role=_role())
    assert box.char_count == 1
    assert box.chars[0].name == "娜娜莉"
    assert box.chars[0].quality == "S"


def test_parse_exastris_box_empty():
    box = parse_exastris_box({"code": 0, "data": []}, role=_role())
    assert box.char_count == 0
    assert box.chars == []
