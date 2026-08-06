"""明日方舟签到周期日历解析。"""

from datetime import datetime

from app.core.timeutil import BEIJING
from app.services.skland_calendar import parse_arknights_attendance_calendar


def test_parse_calendar_list_with_records() -> None:
    # 北京 2026-08-06：本月已领 2 次 → 第 1、2 天 claimed
    now = datetime(2026, 8, 6, 12, 0, tzinfo=BEIJING)
    claim1 = int(datetime(2026, 8, 1, 10, 0, tzinfo=BEIJING).timestamp())
    claim2 = int(datetime(2026, 8, 5, 10, 0, tzinfo=BEIJING).timestamp())
    today_ts = int(datetime(2026, 8, 6, 9, 0, tzinfo=BEIJING).timestamp())

    resp = {
        "code": 0,
        "data": {
            "resourceInfoMap": {
                "2002": {
                    "id": "2002",
                    "type": "CARD_EXP",
                    "name": "初级作战记录",
                },
                "4003": {"id": "4003", "type": "DIAMOND_SHD", "name": "合成玉"},
            },
            "calendar": [
                {"resourceId": "4003", "count": 100},
                {
                    "resource": {
                        "id": "2002",
                        "type": "CARD_EXP",
                        "name": "初级作战记录",
                    },
                    "count": 3,
                },
                {"resourceId": "4003", "count": 300},
            ],
            "records": [
                {"ts": claim1, "resourceId": "4003"},
                {"ts": claim2, "resourceId": "4003"},
                {"ts": today_ts, "resourceId": "4003"},
            ],
        },
    }
    out = parse_arknights_attendance_calendar(resp, now=now)
    assert out["total_days"] == 3
    assert out["claimed_days"] == 3  # 3 records in August
    assert out["has_today_claim"] is True
    assert out["days"][0]["claimed"] is True
    assert out["days"][1]["claimed"] is True
    assert out["days"][2]["claimed"] is True
    assert out["days"][0]["awards"][0]["name"] == "合成玉"
    assert out["days"][0]["awards"][0]["icon_url"].endswith("/DIAMOND_SHD.png")
    assert out["days"][1]["awards"][0]["name"] == "初级作战记录"
    assert out["days"][1]["awards"][0]["icon_url"].endswith(
        "/sprite_exp_card_t2.png"
    )
    assert out["days"][1]["awards"][0]["count"] == 3


def test_parse_calendar_dict_keys() -> None:
    now = datetime(2026, 8, 6, 12, 0, tzinfo=BEIJING)
    resp = {
        "code": 0,
        "data": {
            "calendar": {
                "2": {
                    "resource": {"type": "GOLD", "name": "龙门币"},
                    "count": 5,
                },
                "1": {
                    "resource": {"type": "EXP_PLAYER", "name": "作战记录"},
                    "count": 1,
                },
            },
            "records": [],
        },
    }
    out = parse_arknights_attendance_calendar(resp, now=now)
    assert out["total_days"] == 2
    assert out["claimed_days"] == 0
    assert out["days"][0]["day"] == 1
    assert out["days"][0]["awards"][0]["name"] == "作战记录"
    assert out["days"][1]["awards"][0]["name"] == "龙门币"
    assert out["days"][0]["claimed"] is False


def test_parse_explicit_claimed_flags() -> None:
    now = datetime(2026, 8, 6, 12, 0, tzinfo=BEIJING)
    resp = {
        "code": 0,
        "data": {
            "calendar": [
                {"done": True, "resource": {"name": "A", "type": "X"}, "count": 1},
                {"done": False, "resource": {"name": "B", "type": "Y"}, "count": 2},
            ],
            "records": [],
        },
    }
    out = parse_arknights_attendance_calendar(resp, now=now)
    assert out["claimed_days"] == 1
    assert out["days"][0]["claimed"] is True
    assert out["days"][1]["claimed"] is False
    assert out["progress_reliable"] is True


def test_parse_unreliable_does_not_fake_claimed_from_day_count() -> None:
    """B 服：全 done=false 且无 records 时不可用本地天数冒充周期进度。"""
    now = datetime(2026, 8, 6, 12, 0, tzinfo=BEIJING)
    resp = {
        "code": 0,
        "data": {
            "calendar": [
                {
                    "resourceId": "2002",
                    "type": "daily",
                    "count": 3,
                    "available": True,
                    "done": False,
                },
                {
                    "resourceId": "4001",
                    "type": "daily",
                    "count": 500,
                    "available": False,
                    "done": False,
                },
                {
                    "resourceId": "4003",
                    "type": "daily",
                    "count": 80,
                    "available": False,
                    "done": False,
                },
            ],
            "records": [],
            "resourceInfoMap": {
                "2002": {"id": "2002", "type": "CARD_EXP", "name": "初级作战记录"},
                "4001": {"id": "4001", "type": "GOLD", "name": "龙门币"},
                "4003": {"id": "4003", "type": "DIAMOND_SHD", "name": "合成玉"},
            },
        },
    }
    out = parse_arknights_attendance_calendar(
        resp, now=now, fallback_has_today=True
    )
    assert out["progress_reliable"] is False
    assert out["claimed_days"] == 0
    assert out["has_today_claim"] is True
    assert all(not d["claimed"] for d in out["days"])


def test_infer_claimed_from_unique_today_award() -> None:
    now = datetime(2026, 8, 6, 12, 0, tzinfo=BEIJING)
    resp = {
        "code": 0,
        "data": {
            "calendar": [
                {
                    "resourceId": "2002",
                    "type": "daily",
                    "count": 3,
                    "done": False,
                },
                {
                    "resourceId": "4001",
                    "type": "daily",
                    "count": 500,
                    "done": False,
                },
                {
                    "resourceId": "31043",
                    "type": "daily",
                    "count": 1,
                    "done": False,
                },
            ],
            "records": [],
            "resourceInfoMap": {
                "2002": {"id": "2002", "type": "CARD_EXP", "name": "初级作战记录"},
                "4001": {"id": "4001", "type": "GOLD", "name": "龙门币"},
                "31043": {"id": "31043", "type": "MATERIAL", "name": "半自然溶剂"},
            },
        },
    }
    out = parse_arknights_attendance_calendar(
        resp,
        now=now,
        fallback_has_today=True,
        fallback_today_awards=[{"resource_id": "4001", "name": "龙门币", "count": 500}],
    )
    assert out["progress_reliable"] is False
    assert out["claimed_days"] == 2
    assert out["days"][0]["claimed"] is True
    assert out["days"][1]["claimed"] is True
    assert out["days"][2]["claimed"] is False


def test_count_claims_unique_days() -> None:
    """同一天 first + daily 两条 records 只计 1 天。"""
    now = datetime(2026, 8, 6, 12, 0, tzinfo=BEIJING)
    day_ts = int(datetime(2026, 8, 3, 0, 0, tzinfo=BEIJING).timestamp())
    from app.services.skland_calendar import count_claims_this_month

    n = count_claims_this_month(
        [
            {"ts": str(day_ts), "type": "first", "resourceId": "4003"},
            {"ts": str(day_ts), "type": "daily", "resourceId": "2002"},
        ],
        now=now,
    )
    assert n == 1
