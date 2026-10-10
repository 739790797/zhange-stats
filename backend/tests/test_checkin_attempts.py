"""调度签到当日重试账：退避、上限、终态，以及进队列前的过滤。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.ephemeral_kv import ephemeral_get, reset_ephemeral_kv_for_tests
from app.core.timeutil import BEIJING
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.skland import SklandBind, SklandCheckinLog
from app.services.checkin import attempts as att
from app.services.checkin.queue import CheckinQueueItem
from app.services.checkin.role_prefs import collect_checkin_job_targets

PLATFORM = "skland"
ROLE = ("arknights", "1")


@pytest.fixture(autouse=True)
def _fresh_kv():
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()


def _at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 9, 24, hour, minute, second, tzinfo=BEIJING)


def _item(member_id: int, role=ROLE, hour: int = 0, minute: int = 5) -> CheckinQueueItem:
    return CheckinQueueItem(member_id=member_id, role_key=role, hour=hour, minute=minute)


def test_classify_terminal_failure() -> None:
    assert att.classify_terminal_failure(["凭证可能已失效，请重新绑定森空岛（401）"]) == att.TERMINAL_AUTH
    assert att.classify_terminal_failure(["登录已失效，请重新绑定"]) == att.TERMINAL_AUTH
    assert att.classify_terminal_failure(["签到触发人机验证，请稍后在米游社 App 内完成一次签到"]) == (
        att.TERMINAL_CAPTCHA
    )
    assert att.classify_terminal_failure(["Geetest required"]) == att.TERMINAL_CAPTCHA
    assert att.classify_terminal_failure(["网络异常，请稍后重试（timeout）"]) is None
    assert att.classify_terminal_failure([None, ""]) is None


def test_backoff_1_3_9_then_cap() -> None:
    t0 = _at(0, 5, 40)
    att.record_checkin_attempt(PLATFORM, 1, {ROLE}, now=t0)
    state = att.load_attempts(PLATFORM, 1, now=t0)["arknights/1"]
    assert state.attempts == 1
    # 按整分钟对齐：00:05:40 失败 → 00:06:00 可再试
    assert not state.ready(_at(0, 5, 59))
    assert state.ready(_at(0, 6))

    att.record_checkin_attempt(PLATFORM, 1, {ROLE}, now=_at(0, 6))
    state = att.load_attempts(PLATFORM, 1, now=t0)["arknights/1"]
    assert not state.ready(_at(0, 8, 59))
    assert state.ready(_at(0, 9))

    att.record_checkin_attempt(PLATFORM, 1, {ROLE}, now=_at(0, 9))
    state = att.load_attempts(PLATFORM, 1, now=t0)["arknights/1"]
    assert not state.ready(_at(0, 17))
    assert state.ready(_at(0, 18))

    att.record_checkin_attempt(PLATFORM, 1, {ROLE}, now=_at(0, 18))
    state = att.load_attempts(PLATFORM, 1, now=t0)["arknights/1"]
    assert state.attempts == att.MAX_ATTEMPTS_PER_DAY
    assert not state.ready(_at(23, 59))


def test_terminal_failure_stops_for_the_day_but_not_tomorrow() -> None:
    att.record_checkin_attempt(PLATFORM, 1, {ROLE}, now=_at(0, 5), terminal=att.TERMINAL_AUTH)
    state = att.load_attempts(PLATFORM, 1, now=_at(0, 5))["arknights/1"]
    assert state.terminal == att.TERMINAL_AUTH
    assert not state.ready(_at(12, 0))
    tomorrow = _at(0, 5) + timedelta(days=1)
    assert att.load_attempts(PLATFORM, 1, now=tomorrow) == {}


def test_ledger_ttl_ends_with_the_beijing_day(monkeypatch) -> None:
    seen: dict[str, int] = {}

    def fake_set(key: str, value: str, *, ttl_sec: int) -> None:
        seen["ttl"] = ttl_sec

    monkeypatch.setattr(att, "ephemeral_set", fake_set)
    att.record_checkin_attempt(PLATFORM, 1, None, now=_at(23, 0))
    assert 3600 <= seen["ttl"] <= 3600 + 120


def test_outcome_success_records_nothing() -> None:
    out = {"ok": True, "results": [{"game_code": "arknights", "role_uid": "1", "status": "ok"}]}
    att.record_checkin_outcome(PLATFORM, 1, {ROLE}, out, now=_at(0, 5))
    assert att.load_attempts(PLATFORM, 1, now=_at(0, 5)) == {}
    att.record_checkin_outcome(PLATFORM, 2, None, {"ok": True, "results": []}, now=_at(0, 5))
    assert ephemeral_get(att._kv_key(PLATFORM, 2, _at(0, 5))) is None


def test_outcome_skipped_is_done_for_the_day() -> None:
    att.record_checkin_outcome(
        PLATFORM, 1, {ROLE}, {"skipped": True, "ok": True, "results": []}, now=_at(0, 5)
    )
    assert att.load_attempts(PLATFORM, 1, now=_at(0, 5))["arknights/1"].terminal == att.TERMINAL_DONE


def test_outcome_no_targets_and_vanished_role_are_terminal() -> None:
    att.record_checkin_outcome(
        PLATFORM, 1, None, {"ok": False, "no_targets": True, "results": []}, now=_at(0, 5)
    )
    assert att.load_attempts(PLATFORM, 1, now=_at(0, 5))["*"].terminal == att.TERMINAL_NO_ROLES

    other = ("endfield", "9")
    out = {
        "ok": True,
        "results": [{"game_code": "arknights", "role_uid": "1", "status": "ok"}],
    }
    att.record_checkin_outcome(PLATFORM, 2, {ROLE, other}, out, now=_at(0, 5))
    states = att.load_attempts(PLATFORM, 2, now=_at(0, 5))
    assert set(states) == {"endfield/9"}
    assert states["endfield/9"].terminal == att.TERMINAL_NO_ROLES


def test_outcome_per_role_failure_classifies_message() -> None:
    other = ("endfield", "9")
    out = {
        "ok": False,
        "results": [
            {"game_code": "arknights", "role_uid": "1", "status": "error", "message": "网络异常"},
            {
                "game_code": "endfield",
                "role_uid": "9",
                "status": "error",
                "message": "凭证可能已失效，请重新绑定森空岛",
            },
        ],
    }
    att.record_checkin_outcome(PLATFORM, 1, {ROLE, other}, out, now=_at(0, 5))
    states = att.load_attempts(PLATFORM, 1, now=_at(0, 5))
    assert states["arknights/1"].terminal is None
    assert states["arknights/1"].attempts == 1
    assert states["endfield/9"].terminal == att.TERMINAL_AUTH


def test_filter_retry_ready_drops_backoff_and_carries_attempts() -> None:
    att.record_checkin_attempt(PLATFORM, 1, {ROLE}, now=_at(0, 5))
    att.record_checkin_attempt(PLATFORM, 2, {ROLE}, now=_at(0, 5), terminal=att.TERMINAL_CAPTCHA)
    items = [_item(1), _item(2), _item(3)]

    during_backoff = att.filter_retry_ready(PLATFORM, items, now=_at(0, 5, 30))
    assert [i.member_id for i in during_backoff] == [3]

    after = att.filter_retry_ready(PLATFORM, items, now=_at(0, 6))
    assert [(i.member_id, i.attempts) for i in after] == [(1, 1), (3, 0)]


def test_clear_checkin_attempts() -> None:
    att.record_checkin_attempt(PLATFORM, 1, None, now=_at(0, 5), terminal=att.TERMINAL_AUTH)
    att.clear_checkin_attempts(PLATFORM, 1, now=_at(0, 5))
    assert att.load_attempts(PLATFORM, 1, now=_at(0, 5)) == {}


def _db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _member(db: Session, mid: int, *, legacy_hour: int | None = None, legacy_minute: int = 5) -> None:
    db.add(Member(id=mid, nickname=f"m{mid}"))
    db.add(
        SklandBind(
            member_id=mid,
            token_enc="x",
            auto_checkin=legacy_hour is not None,
            checkin_hour=legacy_hour if legacy_hour is not None else 0,
            checkin_minute=legacy_minute,
        )
    )


def _pref(db: Session, mid: int, uid: str, hour: int, minute: int, *, enabled: bool = True) -> None:
    db.add(
        CheckinRolePref(
            platform=PLATFORM,
            member_id=mid,
            game_code="arknights",
            role_uid=uid,
            included=True,
            enabled=enabled,
            checkin_hour=hour,
            checkin_minute=minute,
        )
    )


def _due(db: Session, now: datetime) -> dict:
    return collect_checkin_job_targets(
        db,
        platform=PLATFORM,
        bind_model=SklandBind,
        due_only=True,
        log_model=SklandCheckinLog,
        now=now,
    )


def test_collect_due_targets_prefilters_window_in_sql_and_batches_legacy() -> None:
    db = _db()
    _member(db, 1)
    _pref(db, 1, "a", 0, 5)
    _pref(db, 1, "b", 8, 0)
    _member(db, 2, legacy_hour=0, legacy_minute=5)
    _member(db, 3, legacy_hour=0, legacy_minute=5)
    # 有 pref 的成员不再走旧 bind 全量，即便 pref 都关着
    _pref(db, 3, "c", 0, 5, enabled=False)
    _member(db, 4, legacy_hour=23, legacy_minute=50)
    db.commit()

    # 窗口最后一分钟取完；08:00 的角色与 23:50 的旧绑定不在窗口内
    assert _due(db, _at(0, 34)) == {1: {("arknights", "a")}, 2: None}
    # 跨午夜：23:50 的窗口在 00:10 仍开着，且剩余分钟更少先出队
    assert _due(db, _at(0, 10)) == {4: None, 1: {("arknights", "a")}}
    assert _due(db, _at(0, 35)) == {}


def test_collect_due_targets_skips_backoff_and_terminal_members() -> None:
    db = _db()
    for mid in (1, 2, 3):
        _member(db, mid)
        _pref(db, mid, str(mid), 0, 5)
    db.commit()
    now = _at(0, 34)
    att.record_checkin_attempt(PLATFORM, 1, {("arknights", "1")}, now=_at(0, 34))
    att.record_checkin_attempt(
        PLATFORM, 2, {("arknights", "2")}, now=_at(0, 20), terminal=att.TERMINAL_AUTH
    )

    assert _due(db, now) == {3: {("arknights", "3")}}


def test_collect_due_targets_keeps_action_success_filter() -> None:
    db = _db()
    _member(db, 1)
    _pref(db, 1, "1", 0, 5)
    db.add(
        SklandCheckinLog(
            member_id=1,
            bind_id=1,
            game_code="arknights",
            game_name="明日方舟",
            role_uid="1",
            status="ok",
            message="",
            checkin_date=_at(0, 34).date(),
            checked_at=_at(0, 6).replace(tzinfo=None),
            source="action",
        )
    )
    db.commit()
    assert _due(db, _at(0, 34)) == {}
