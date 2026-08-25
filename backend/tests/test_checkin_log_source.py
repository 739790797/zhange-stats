"""签到 logs source：status 不算执行记录。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.checkin.common import (
    LOG_SOURCE_ACTION,
    LOG_SOURCE_STATUS,
    CheckinResult,
    upsert_day_checkin_logs,
)


class _FakeLog:
    # SQLAlchemy filter 会读这些类属性
    member_id = object()
    checkin_date = object()
    game_code = object()
    role_uid = object()
    awards_json = object()
    source = object()

    def __init__(self, **kw):
        self.source = LOG_SOURCE_STATUS
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def one_or_none(self):
        return self._row


class _FakeDb:
    def __init__(self, existing=None):
        self.added = []
        self._existing = existing

    def query(self, model):
        return _FakeQuery(self._existing)

    def add(self, row):
        self.added.append(row)


def _result() -> CheckinResult:
    return CheckinResult(
        game_code="arknights",
        game_name="明日方舟",
        role_uid="1",
        role_name="r",
        channel_name="官服",
        status="already",
        message="今日已签到",
        awards_text="合成玉x80",
    )


def test_upsert_status_then_action_keeps_action_source() -> None:
    db = _FakeDb()
    upsert_day_checkin_logs(
        db,
        _FakeLog,
        member_id=1,
        bind_id=1,
        checkin_date=date(2026, 8, 6),
        results=[_result()],
        now=date(2026, 8, 6),
        source=LOG_SOURCE_STATUS,
    )
    assert len(db.added) == 1
    assert db.added[0].source == LOG_SOURCE_STATUS

    row = db.added[0]
    upsert_day_checkin_logs(
        _FakeDb(existing=row),
        _FakeLog,
        member_id=1,
        bind_id=1,
        checkin_date=date(2026, 8, 6),
        results=[_result()],
        now=date(2026, 8, 6),
        source=LOG_SOURCE_ACTION,
    )
    assert row.source == LOG_SOURCE_ACTION

    upsert_day_checkin_logs(
        _FakeDb(existing=row),
        _FakeLog,
        member_id=1,
        bind_id=1,
        checkin_date=date(2026, 8, 6),
        results=[_result()],
        now=date(2026, 8, 6),
        source=LOG_SOURCE_STATUS,
    )
    assert row.source == LOG_SOURCE_ACTION


def test_arknights_action_already_empty_keeps_prior_awards() -> None:
    """B 服重复签到常无 awards：不得冲掉此前 POST 落库的奖励。"""
    row = _FakeLog(
        member_id=1,
        bind_id=1,
        game_code="arknights",
        game_name="明日方舟",
        role_uid="1",
        role_name="r",
        channel_name="B服",
        status="ok",
        message="合成玉x80",
        awards_text="合成玉x80",
        awards_json='[{"name":"合成玉","count":80}]',
        checkin_date=date(2026, 8, 6),
        checked_at=date(2026, 8, 6),
        source=LOG_SOURCE_ACTION,
    )
    empty_already = CheckinResult(
        game_code="arknights",
        game_name="明日方舟",
        role_uid="1",
        role_name="r",
        channel_name="B服",
        status="already",
        message="",
        awards_text=None,
        awards=None,
    )
    upsert_day_checkin_logs(
        _FakeDb(existing=row),
        _FakeLog,
        member_id=1,
        bind_id=1,
        checkin_date=date(2026, 8, 6),
        results=[empty_already],
        now=date(2026, 8, 6),
        source=LOG_SOURCE_ACTION,
    )
    assert row.status == "already"
    assert row.awards_text == "合成玉x80"
    assert row.message == "合成玉x80"
    assert "合成玉" in (row.awards_json or "")
