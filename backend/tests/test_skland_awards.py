"""森空岛方舟奖励解析与图标 URL。"""

from app.services.skland_awards import (
    arknights_awards_from_sign_resp,
    arknights_item_icon_url,
    format_award_items,
)


def test_arknights_item_icon_url() -> None:
    assert (
        arknights_item_icon_url("DIAMOND_SHD")
        == "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/item/DIAMOND_SHD.png"
    )
    assert arknights_item_icon_url("") is None
    assert arknights_item_icon_url("../x") is None
    assert arknights_item_icon_url("a/b") is None


def test_arknights_item_icon_url_by_resource_id() -> None:
    """Skland type 多为分类（CARD_EXP），图标应按 itemId→iconId。"""
    url = arknights_item_icon_url("CARD_EXP", resource_id="2002")
    assert url is not None
    assert url.endswith("/item/sprite_exp_card_t2.png")
    skill = arknights_item_icon_url("MATERIAL", resource_id="3302")
    assert skill is not None
    assert skill.endswith("/item/MTL_SKILL2.png")


def test_format_award_items_with_icons() -> None:
    text, items = format_award_items(
        [
            {
                "resource": {
                    "id": "4003",
                    "type": "DIAMOND_SHD",
                    "name": "合成玉",
                    "rarity": 4,
                },
                "count": 80,
            }
        ],
        with_icons=True,
    )
    assert text == "合成玉x80"
    assert len(items) == 1
    assert items[0]["name"] == "合成玉"
    assert items[0]["count"] == 80
    assert items[0]["resource_type"] == "DIAMOND_SHD"
    assert items[0]["icon_url"].endswith("/item/DIAMOND_SHD.png")


def test_arknights_awards_from_sign_response() -> None:
    text, items = arknights_awards_from_sign_resp(
        {
            "code": 0,
            "data": {
                "awards": [
                    {
                        "resource": {
                            "id": "4003",
                            "type": "DIAMOND_SHD",
                            "name": "合成玉",
                        },
                        "count": 80,
                    }
                ]
            },
        }
    )
    assert text == "合成玉x80"
    assert items[0]["icon_url"]
