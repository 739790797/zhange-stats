"""game-schedule 代理：解析、落库与分类。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from app.core.timeutil import BEIJING
from app.services import game_schedule as gs


def _mock_db_with_raw(payload: dict) -> MagicMock:
    import json

    row = MagicMock()
    row.raw_json = json.dumps(payload)
    row.synced_at = datetime(2026, 8, 24, 10, 0, tzinfo=BEIJING)
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = row
    return db


def test_normalize_and_classify_ongoing() -> None:
    raw = {
        "id": "1",
        "title": "测试活动",
        "start_time": "2026-08-01 04:00",
        "end_time": "2026-09-01 03:59",
        "banner": "https://example.com/a.jpg",
        "linkUrl": "https://example.com",
        "type": "活动",
    }
    event = gs._normalize_event(raw, game="arknights")
    assert event is not None
    assert event["title"] == "测试活动"
    assert event["link_url"] == "https://example.com"
    assert event["event_type"] == "活动"
    at = datetime(2026, 8, 15, 12, 0, tzinfo=BEIJING)
    assert gs._classify(event, at=at) == "ongoing"


def test_strip_title_ordinal() -> None:
    assert gs._strip_title_ordinal("一、SideStory「墟」") == "SideStory「墟」"
    assert gs._strip_title_ordinal("十一、「夏日嘉年华」") == "「夏日嘉年华」"
    assert gs._strip_title_ordinal("六、【联合行动】开启") == "【联合行动】开启"
    assert gs._strip_title_ordinal("协议重连") == "协议重连"
    event = gs._normalize_event(
        {
            "id": "2",
            "title": "四、[联合行动] 特选干员定向寻访开启",
            "start_time": "2026-08-01 04:00",
            "end_time": "2026-09-01 03:59",
        },
        game="arknights",
    )
    assert event is not None
    assert event["title"] == "[联合行动] 特选干员定向寻访开启"


def test_is_permanent_event_by_span() -> None:
    permanent = {
        "title": "于此启程",
        "start_time": "2025-12-09 04:00",
        "end_time": "2031-08-24 02:55",
        "event_type": "新手活动",
    }
    limited = {
        "title": "理智补给",
        "start_time": "2026-08-26 04:00",
        "end_time": "2026-09-02 04:00",
        "event_type": "限时活动",
    }
    assert gs._is_permanent_event(permanent) is True
    assert gs._is_permanent_event(limited) is False


def test_get_game_events_skips_permanent(monkeypatch) -> None:
    payload = {
        "code": 200,
        "data": [
            {
                "id": "perm",
                "title": "于此启程",
                "start_time": "2025-12-09 04:00",
                "end_time": "2031-08-24 02:55",
                "type": "新手活动",
            },
            {
                "id": "lim",
                "title": "理智补给",
                "start_time": "2026-08-26 04:00",
                "end_time": "2026-09-02 04:00",
                "type": "限时活动",
            },
        ],
    }
    db = _mock_db_with_raw(payload)
    monkeypatch.setattr(
        gs,
        "beijing_now",
        lambda: datetime(2026, 8, 24, 12, 0, tzinfo=BEIJING),
    )
    out = gs.get_game_events(db, "endfield", force=False)

    titles = [e["title"] for e in out["events"]]
    assert titles == ["理智补给"]
    assert [e["title"] for e in out["permanent_events"]] == ["于此启程"]
    assert out["permanent_count"] == 1
    assert out["ongoing_count"] + out["upcoming_count"] == 1


def test_get_game_events_filters_ended(monkeypatch) -> None:
    payload = {
        "code": 200,
        "data": [
            {
                "id": "old",
                "title": "已结束",
                "start_time": "2026-01-01 04:00",
                "end_time": "2026-01-10 03:59",
            },
            {
                "id": "now",
                "title": "进行中",
                "start_time": "2026-08-01 04:00",
                "end_time": "2026-09-01 03:59",
            },
            {
                "id": "soon",
                "title": "未开始",
                "start_time": "2026-09-10 04:00",
                "end_time": "2026-09-20 03:59",
            },
        ],
    }
    db = _mock_db_with_raw(payload)
    monkeypatch.setattr(
        gs,
        "beijing_now",
        lambda: datetime(2026, 8, 15, 12, 0, tzinfo=BEIJING),
    )
    out = gs.get_game_events(db, "arknights", force=False)

    titles = [e["title"] for e in out["events"]]
    assert titles == ["进行中", "未开始"]
    assert out["ongoing_count"] == 1
    assert out["upcoming_count"] == 1


def test_get_game_events_force_sync(monkeypatch) -> None:
    payload = {
        "code": 200,
        "data": [
            {
                "id": "now",
                "title": "进行中",
                "start_time": "2026-08-01 04:00",
                "end_time": "2026-09-01 03:59",
            },
        ],
    }
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    monkeypatch.setattr(gs, "sync_game_schedule", lambda _db, game: {"game": game})
    monkeypatch.setattr(
        gs,
        "get_game_schedule_raw",
        lambda _db, game: _mock_db_with_raw(payload).query().filter().one_or_none(),
    )
    monkeypatch.setattr(
        gs,
        "beijing_now",
        lambda: datetime(2026, 8, 15, 12, 0, tzinfo=BEIJING),
    )
    out = gs.get_game_events(db, "arknights", force=True)
    assert out["events"][0]["title"] == "进行中"
