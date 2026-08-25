"""塔吉多签到周期日历解析。"""

from app.services.taygedo.calendar import parse_taygedo_attendance_calendar


def test_parse_rewards_with_days() -> None:
    raw = {
        "state": {"todaySign": True, "days": 3, "month": 8, "day": 6},
        "rewards": [
            {"name": "甲硬币", "num": 10000, "icon": "https://example.com/a.png"},
            {"name": "环石", "num": 20},
            {"name": "心迷宫", "num": 1},
            {"name": "未签奖励", "num": 5},
        ],
    }
    out = parse_taygedo_attendance_calendar(raw)
    assert out["total_days"] == 4
    assert out["claimed_days"] == 3
    assert out["has_today_claim"] is True
    assert out["progress_reliable"] is True
    assert [d["claimed"] for d in out["days"]] == [True, True, True, False]
    assert out["days"][0]["awards"][0]["name"] == "甲硬币"
    assert out["days"][0]["awards"][0]["count"] == 10000
    assert out["days"][0]["awards"][0]["icon_url"] == "https://example.com/a.png"


def test_parse_not_signed_today() -> None:
    raw = {
        "state": {"todaySign": False, "days": 2, "month": 8},
        "rewards": [
            {"name": "A", "num": 1},
            {"name": "B", "num": 2},
            {"name": "C", "num": 3},
        ],
    }
    out = parse_taygedo_attendance_calendar(raw)
    assert out["has_today_claim"] is False
    assert out["claimed_days"] == 2
    assert [d["claimed"] for d in out["days"]] == [True, True, False]


def test_fallback_has_today() -> None:
    raw = {
        "state": {"todaySign": False, "days": 0},
        "rewards": [{"name": "A", "num": 1}],
    }
    out = parse_taygedo_attendance_calendar(raw, fallback_has_today=True)
    assert out["has_today_claim"] is True
    assert out["claimed_days"] >= 1
