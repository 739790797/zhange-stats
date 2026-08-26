"""米游社游戏福利签到日历解析。"""

from app.services.mihoyo.calendar import (
    parse_mihoyo_attendance_calendar,
    parse_today_mihoyo_awards,
    select_today_awards,
)


def test_parse_home_awards_and_info() -> None:
    raw = {
        "info": {
            "is_sign": True,
            "total_sign_day": 3,
            "sign_cnt_missed": 0,
            "today": "3",
        },
        "home": {
            "awards": [
                {"name": "原石", "cnt": 20, "icon": "https://example.com/a.png"},
                {"name": "摩拉", "cnt": 10000},
                {"name": "冒险家的经验", "cnt": 3},
                {"name": "精锻用矿", "cnt": 2},
            ]
        },
    }
    out = parse_mihoyo_attendance_calendar(raw)
    assert out["total_days"] == 4
    assert out["claimed_days"] == 3
    assert out["has_today_claim"] is True
    assert out["progress_reliable"] is True
    assert [d["day"] for d in out["days"]] == [1, 2, 3, 4]
    assert [d["claimed"] for d in out["days"]] == [True, True, True, False]
    assert out["days"][0]["awards"][0]["name"] == "原石"
    assert out["days"][0]["awards"][0]["count"] == 20
    assert out["days"][0]["awards"][0]["icon_url"] == "https://example.com/a.png"


def test_parse_not_signed_today() -> None:
    raw = {
        "info": {"is_sign": False, "total_sign_day": 2, "today": "3"},
        "home": {
            "awards": [
                {"name": "A", "cnt": 1},
                {"name": "B", "cnt": 2},
                {"name": "C", "cnt": 3},
            ]
        },
    }
    out = parse_mihoyo_attendance_calendar(raw)
    assert out["has_today_claim"] is False
    assert out["claimed_days"] == 2
    assert [d["claimed"] for d in out["days"]] == [True, True, False]


def test_fallback_has_today() -> None:
    raw = {
        "info": {"is_sign": False, "total_sign_day": 0},
        "home": {"awards": [{"name": "A", "cnt": 1}]},
    }
    out = parse_mihoyo_attendance_calendar(raw, fallback_has_today=True)
    assert out["has_today_claim"] is True
    assert out["claimed_days"] >= 1


def test_select_today_awards_from_month_list() -> None:
    awards = [
        {"name": "A", "cnt": 1},
        {"name": "B", "cnt": 2},
        {"name": "C", "cnt": 3},
    ]
    signed = select_today_awards(awards, signed=True, total_sign_day=2)
    assert len(signed) == 1
    assert signed[0]["name"] == "B"
    pending = select_today_awards(awards, signed=False, total_sign_day=2)
    assert pending[0]["name"] == "C"


def test_missed_days_mark_unreliable() -> None:
    raw = {
        "info": {"is_sign": True, "total_sign_day": 10, "sign_cnt_missed": 2},
        "home": {"awards": [{"name": "A", "cnt": 1}]},
    }
    out = parse_mihoyo_attendance_calendar(raw)
    assert out["progress_reliable"] is False


def test_parse_today_awards_prefers_home_icons() -> None:
    text, items = parse_today_mihoyo_awards(
        {"is_sign": True, "total_sign_day": 2, "today": "2"},
        {
            "awards": [
                {"name": "A", "cnt": 1, "icon": "https://example.com/a.png"},
                {"name": "原石", "cnt": 20, "icon": "https://example.com/p.png"},
                {"name": "C", "cnt": 3},
            ]
        },
    )
    assert text == "原石×20"
    assert len(items) == 1
    assert items[0]["icon_url"] == "https://example.com/p.png"


def test_parse_today_awards_empty_without_home() -> None:
    text, items = parse_today_mihoyo_awards(
        {"is_sign": True, "total_sign_day": 5, "today": "5"}
    )
    assert text is None
    assert items == []
