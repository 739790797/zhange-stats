"""库街区鸣潮 / 战双签到周期日历解析。"""

from app.services.kujiequ_calendar import parse_kujiequ_attendance_calendar


def test_parse_sign_in_goods_configs() -> None:
    raw = {
        "init": {
            "isSigIn": True,
            "sigInNum": 4,
            "signInGoodsConfigs": [
                {
                    "id": 2422,  # 上游全局 id，勿当第几天
                    "goodsName": "中级共鸣促剂",
                    "goodsNum": 2,
                    "goodsUrl": "https://example.com/a.png",
                },
                {
                    "id": 2423,
                    "goodsName": "中级能源核心",
                    "goodsNum": 2,
                },
                {"id": 2424, "goodsName": "星声", "goodsNum": 20},
                {"id": 2425, "goodsName": "贝币", "goodsNum": 8000},
                {"id": 2426, "goodsName": "中级密音筒", "goodsNum": 1},
            ],
        },
        "records": [],
    }
    out = parse_kujiequ_attendance_calendar(raw)
    assert out["total_days"] == 5
    assert out["claimed_days"] == 4
    assert out["has_today_claim"] is True
    assert out["progress_reliable"] is True
    assert [d["day"] for d in out["days"]] == [1, 2, 3, 4, 5]
    assert [d["claimed"] for d in out["days"]] == [True, True, True, True, False]
    assert out["days"][3]["awards"][0]["name"] == "贝币"
    assert out["days"][3]["awards"][0]["count"] == 8000
    assert out["days"][0]["awards"][0]["icon_url"] == "https://example.com/a.png"


def test_parse_not_signed_today() -> None:
    raw = {
        "init": {
            "isSigIn": False,
            "sigInNum": 2,
            "signInGoodsConfigs": [
                {"id": 1, "goodsName": "A", "goodsNum": 1},
                {"id": 2, "goodsName": "B", "goodsNum": 2},
                {"id": 3, "goodsName": "C", "goodsNum": 3},
            ],
        },
        "records": [],
    }
    out = parse_kujiequ_attendance_calendar(raw)
    assert out["has_today_claim"] is False
    assert out["claimed_days"] == 2
    assert [d["claimed"] for d in out["days"]] == [True, True, False]


def test_fallback_has_today() -> None:
    raw = {
        "init": {
            "isSigIn": False,
            "sigInNum": 0,
            "signInGoodsConfigs": [{"id": 1, "goodsName": "A", "goodsNum": 1}],
        },
        "records": [],
    }
    out = parse_kujiequ_attendance_calendar(raw, fallback_has_today=True)
    assert out["has_today_claim"] is True
    assert out["claimed_days"] >= 1
