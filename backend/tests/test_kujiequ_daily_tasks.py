"""库街区每日任务文案与商品解析（无网络）。"""

# 先加载 client，避免 attendance↔client 循环导入
import app.services.kujiequ.client  # noqa: F401
from app.services.checkin.common import CheckinResult
from app.services.kujiequ.attendance import (
    _daily_task_counts,
    _tasks_extra_text,
    sort_kujiequ_results,
)
from app.services.kujiequ.client import CommodityItem, _parse_commodity


def test_tasks_extra_text_format() -> None:
    text = _tasks_extra_text(
        view=3,
        like=5,
        share=1,
        gold=50,
        current_daily_gold=50,
        max_daily_gold=80,
    )
    assert "浏览 3/3" in text
    assert "点赞 5/5" in text
    assert "分享 1/1" in text
    assert "库洛币+50" in text
    assert "今日 50/80" in text


def test_sort_kujiequ_results_community_first() -> None:
    rows = [
        CheckinResult(
            game_code="game_3",
            game_name="鸣潮",
            role_uid="1",
            role_name="白衣",
            channel_name="官服",
            status="already",
            message="ok",
        ),
        CheckinResult(
            game_code="game_2",
            game_name="战双",
            role_uid="2",
            role_name="角色",
            channel_name="官服",
            status="already",
            message="ok",
        ),
        CheckinResult(
            game_code="kujiequ",
            game_name="库街区",
            role_uid="u",
            role_name="BaiYii",
            channel_name="社区",
            status="already",
            message="ok",
        ),
    ]
    ordered = sort_kujiequ_results(rows)
    assert [r.game_code for r in ordered] == ["kujiequ", "game_3", "game_2"]


def test_daily_task_counts_from_payload() -> None:
    payload = {
        "currentDailyGold": 30,
        "maxDailyGold": 80,
        "dailyTask": [
            {
                "remark": "用户签到",
                "completeTimes": 1,
                "needActionTimes": 1,
                "gainGold": 30,
            },
            {
                "remark": "浏览3篇帖子",
                "completeTimes": 1,
                "needActionTimes": 3,
                "gainGold": 20,
            },
            {
                "remark": "点赞5次",
                "completeTimes": 0,
                "needActionTimes": 5,
                "gainGold": 20,
            },
            {
                "remark": "分享1次帖子",
                "completeTimes": 0,
                "needActionTimes": 1,
                "gainGold": 10,
            },
        ],
    }
    counts = _daily_task_counts(payload)
    assert counts["view"] == 1
    assert counts["view_need"] == 3
    assert counts["like"] == 0
    assert counts["share"] == 0
    assert counts["gold"] == 30  # 仅已完成的签到
    assert counts["all_done"] is False
    assert counts["current_daily_gold"] == 30


def test_parse_commodity_virtual() -> None:
    item = _parse_commodity(
        {
            "commodityCode": "abc",
            "commodityName": "头像框【测试】",
            "commodityPrice": 1000,
            "commodityType": 1,
            "commodityStatus": 1,  # 官方在售常见为 1
            "gameId": 3,
            "gameName": "鸣潮",
            "pictureUrl": "https://example.com/a.png",
            "commodityLimit": 1,
            "currentUserLimitBuy": 1,
            "totalStock": 9999,
            "totalSurplusStock": 9999,
            "isSellout": False,
        }
    )
    assert isinstance(item, CommodityItem)
    assert item.can_exchange is True
    assert item.to_dict()["commodity_code"] == "abc"


def test_parse_commodity_status_zero_still_ok() -> None:
    item = _parse_commodity(
        {
            "commodityCode": "z0",
            "commodityName": "旧状态可兑",
            "commodityPrice": 100,
            "commodityType": 1,
            "commodityStatus": 0,
            "gameId": 2,
            "totalStock": 10,
            "totalSurplusStock": 10,
            "isSellout": False,
        }
    )
    assert item is not None
    assert item.can_exchange is True


def test_parse_commodity_unlimited_stock_surplus_zero() -> None:
    """totalStock=0 且 surplus=0：不应当成售罄。"""
    item = _parse_commodity(
        {
            "commodityCode": "u1",
            "commodityName": "不限库存",
            "commodityPrice": 100,
            "commodityType": 1,
            "commodityStatus": 1,
            "gameId": 2,
            "totalStock": 0,
            "totalSurplusStock": 0,
            "isSellout": False,
        }
    )
    assert item is not None
    assert item.can_exchange is True


def test_parse_commodity_physical_not_exchangeable() -> None:
    item = _parse_commodity(
        {
            "commodityCode": "phy",
            "commodityName": "金属徽章",
            "commodityPrice": 11800,
            "commodityType": 2,
            "commodityStatus": 0,
            "gameId": 3,
            "currentUserLimitBuy": 1,
            "totalSurplusStock": 10,
        }
    )
    assert item is not None
    assert item.can_exchange is False
