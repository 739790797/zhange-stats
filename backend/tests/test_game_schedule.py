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
    row.source = "game-schedule"
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
    assert out["source"] == "game-schedule"


def _wiki_payload_new_shape() -> dict:
    return {
        "revision": {
            "contentJson": {
                "type": "doc",
                "content": [
                    {
                        "type": "endfieldCardActivityIndex",
                        "attrs": {"id": "section/endfieldCardActivityIndex#0"},
                        "content": [
                            {
                                "type": "endfieldCardActivityIndex__activities",
                                "attrs": {
                                    "name": "雾隐冬梦深林中",
                                    "tags": ["叙事活动"],
                                    "linkTitle": "活动/雾隐冬梦深林中",
                                    "tabImgUrl": "https://assets.fz.wiki/banner.png",
                                    "activityId": "CharacterGuide_typhoeus",
                                    "timeRanges": [
                                        {
                                            "open": "2026/9/2 7:00:00",
                                            "close": "2026/10/15 6:00:00",
                                        }
                                    ],
                                },
                            },
                            {
                                "type": "endfieldCardActivityIndex__activities",
                                "attrs": {
                                    "name": "于此启程",
                                    "tags": ["新手活动"],
                                    "activityId": "activity_gacha_beginner",
                                    "timeRanges": [
                                        {"open": "2025/12/9 4:00:00", "close": ""}
                                    ],
                                },
                            },
                            {
                                "type": "endfieldCardActivityIndex__activities",
                                "attrs": {
                                    "name": "无开始时间",
                                    "activityId": "skip-me",
                                    "timeRanges": [{"open": "", "close": ""}],
                                },
                            },
                        ],
                    }
                ],
            }
        }
    }


def test_parse_wiki_time_unpadded() -> None:
    parsed = gs._parse_schedule_time("2026/9/2 7:00:00")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 9
    assert parsed.day == 2
    assert parsed.hour == 7


def test_wiki_activities_new_shape() -> None:
    data = gs.wiki_activities_to_schedule_data(_wiki_payload_new_shape())
    assert [item["title"] for item in data] == ["雾隐冬梦深林中", "于此启程"]
    limited = data[0]
    assert limited["id"] == "CharacterGuide_typhoeus"
    assert limited["start_time"] == "2026-09-02 07:00"
    assert limited["end_time"] == "2026-10-15 06:00"
    assert limited["type"] == "叙事活动"
    assert limited["banner"] == "https://assets.fz.wiki/banner.png"
    assert limited["linkUrl"].endswith("/%E6%B4%BB%E5%8A%A8/%E9%9B%BE%E9%9A%90%E5%86%AC%E6%A2%A6%E6%B7%B1%E6%9E%97%E4%B8%AD")
    beginner = data[1]
    start = gs._parse_schedule_time(beginner["start_time"])
    end = gs._parse_schedule_time(beginner["end_time"])
    assert start is not None and end is not None
    assert (end - start).days >= gs._PERMANENT_SPAN_DAYS
    assert gs._is_permanent_event(beginner) is True


def test_wiki_activities_old_attrs_shape() -> None:
    payload = {
        "revision": {
            "contentJson": {
                "content": [
                    {
                        "type": "endfieldCardActivityIndex",
                        "attrs": {
                            "activities": [
                                {
                                    "name": "理智补给",
                                    "activityId": "stamina",
                                    "tags": ["限时活动"],
                                    "timeRanges": [
                                        {
                                            "open": "2026/8/26 4:00:00",
                                            "close": "2026/9/2 4:00:00",
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ]
            }
        }
    }
    data = gs.wiki_activities_to_schedule_data(payload)
    assert len(data) == 1
    assert data[0]["title"] == "理智补给"
    assert data[0]["start_time"] == "2026-08-26 04:00"


def test_endfield_empty_schedule_falls_back_to_wiki(monkeypatch) -> None:
    monkeypatch.setattr(
        gs,
        "_download_game_schedule",
        lambda _game: ({"code": 200, "data": []}, "https://gebc.example"),
    )
    wiki_data = gs.wiki_activities_to_schedule_data(_wiki_payload_new_shape())
    monkeypatch.setattr(
        gs,
        "_download_endfield_wiki",
        lambda: ({"code": 200, "data": wiki_data}, "https://api.fz.wiki", gs.SOURCE_FZ_WIKI),
    )
    payload, base, source = gs._download_upstream_payload("endfield")
    assert source == gs.SOURCE_FZ_WIKI
    assert base == "https://api.fz.wiki"
    assert payload["data"][0]["title"] == "雾隐冬梦深林中"


def test_sync_rejects_empty_events(monkeypatch) -> None:
    monkeypatch.setattr(
        gs,
        "_download_upstream_payload",
        lambda _game: ({"code": 200, "data": []}, "https://gebc.example", gs.SOURCE_GAME_SCHEDULE),
    )
    db = MagicMock()
    try:
        gs.sync_game_schedule(db, "arknights")
    except gs.GameScheduleError as exc:
        assert "无有效活动" in exc.message
    else:
        raise AssertionError("expected empty sync to fail")
    db.commit.assert_not_called()
