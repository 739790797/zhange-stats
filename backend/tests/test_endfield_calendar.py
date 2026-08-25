"""终末地签到周期日历解析。"""

from app.services.skland.endfield_calendar import parse_endfield_attendance_calendar


def test_parse_endfield_calendar_done_flags() -> None:
    resp = {
        "code": 0,
        "data": {
            "hasToday": True,
            "calendar": [
                {"awardId": "a1", "done": True, "available": False},
                {"awardId": "a2", "done": False, "available": True},
                {"awardId": "a3", "done": False, "available": False},
            ],
            "resourceInfoMap": {
                "a1": {"id": "a1", "name": "理智药剂", "count": 60},
                "a2": {"id": "a2", "name": "折金票", "count": 200},
                "a3": {"id": "a3", "name": "嵌晶玉", "count": 80},
            },
        },
    }
    out = parse_endfield_attendance_calendar(resp)
    assert out["total_days"] == 3
    assert out["claimed_days"] == 1
    assert out["has_today_claim"] is True
    assert out["progress_reliable"] is True
    assert out["days"][0]["claimed"] is True
    assert out["days"][0]["awards"][0]["name"] == "理智药剂"
    assert out["days"][0]["awards"][0]["count"] == 60
    assert out["days"][1]["claimed"] is False


def test_parse_endfield_calendar_fallback_has_today() -> None:
    resp = {
        "code": 0,
        "data": {
            "calendar": [
                {"awardId": "a1", "done": True, "available": False},
            ],
            "resourceInfoMap": {
                "a1": {"id": "a1", "name": "奖励", "count": 1},
            },
        },
    }
    out = parse_endfield_attendance_calendar(resp, fallback_has_today=True)
    assert out["has_today_claim"] is True


def test_parse_endfield_calendar_empty() -> None:
    out = parse_endfield_attendance_calendar({"code": 1, "data": {}})
    assert out["total_days"] == 0
    assert out["days"] == []
    assert out["progress_reliable"] is False
