"""签到任务列表（管理端 /jobs/user-tasks 与「我的日常」共用）：任务行、分页、上次执行与今日状态。"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.jobs import query_user_checkin_tasks
from app.api.jobs.checkin_queries import attach_last_checkin_to_result_dicts
from app.core.database import Base
from app.core.timeutil import today
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.skland import SklandBind, SklandCheckinLog
from app.models.taygedo import TaygedoBind, TaygedoCheckinLog
from app.models.user import User
from app.services.platform_features import invalidate_feature_cache


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    invalidate_feature_cache()
    yield engine
    engine.dispose()
    invalidate_feature_cache()


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()


def _at(days_ago: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(today() - timedelta(days=days_ago), time(hour, minute))


def _fmt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _member(db, member_id: int, *, user: str | None = None) -> None:
    if user is not None:
        db.add(User(id=member_id, username=user.lower(), display_name=user, password_hash="x"))
    db.add(Member(id=member_id, nickname=f"m{member_id}", user_id=member_id if user else None))
    # 偏好表和 members 之间没有 relationship，flush 不保证先插成员
    db.flush()


def _pref(
    platform: str,
    member_id: int,
    game_code: str,
    role_uid: str,
    *,
    included: bool = True,
    enabled: bool = True,
    at: tuple[int, int] | None = (8, 0),
) -> CheckinRolePref:
    hour, minute = at if at is not None else (None, None)
    return CheckinRolePref(
        platform=platform,
        member_id=member_id,
        game_code=game_code,
        role_uid=role_uid,
        included=included,
        enabled=enabled,
        checkin_hour=hour,
        checkin_minute=minute,
    )


def _log(
    model,
    member_id: int,
    game_code: str,
    role_uid: str,
    *,
    days_ago: int,
    at: tuple[int, int],
    source: str = "action",
    status: str = "ok",
    role_name: str | None = None,
    channel_name: str | None = None,
    awards_text: str | None = None,
    awards: list[dict] | None = None,
):
    checked_at = _at(days_ago, *at)
    return model(
        member_id=member_id,
        bind_id=member_id,
        game_code=game_code,
        game_name=f"{game_code}-name",
        role_uid=role_uid,
        role_name=role_name,
        channel_name=channel_name,
        status=status,
        source=source,
        awards_text=awards_text,
        awards_json=json.dumps(awards, ensure_ascii=False) if awards else None,
        checkin_date=checked_at.date(),
        checked_at=checked_at,
    )


def _seed(db) -> None:
    _member(db, 1, user="Alice")
    _member(db, 2)
    _member(db, 3, user="Bob")
    db.add_all(
        [
            SklandBind(
                id=1,
                member_id=1,
                token_enc="x",
                auto_checkin=True,
                checkin_hour=6,
                checkin_minute=10,
                bound_at=datetime(2026, 1, 1, 10),
            ),
            SklandBind(
                id=2,
                member_id=2,
                token_enc="x",
                auto_checkin=True,
                checkin_hour=5,
                checkin_minute=5,
                bound_at=datetime(2026, 1, 2, 10),
            ),
            TaygedoBind(id=1, member_id=1, credentials_enc="x", bound_at=datetime(2026, 1, 3, 10)),
            TaygedoBind(id=3, member_id=3, credentials_enc="x", bound_at=datetime(2026, 1, 4, 10)),
            _pref("skland", 1, "endfield", "e1", enabled=False, at=(9, 0)),
            _pref("skland", 1, "arknights", "a1", at=(8, 30)),
            _pref("skland", 1, "arknights", "a0", included=False, at=(8, 0)),
            # 没绑定森空岛的成员：偏好不成任务
            _pref("skland", 3, "arknights", "orphan"),
            _pref("taygedo", 1, "1289", "r1", at=(7, 0)),
            _pref("taygedo", 1, "app", "u1", at=(7, 30)),
            _pref("taygedo", 3, "app", "u3", enabled=False, at=None),
            _log(SklandCheckinLog, 1, "arknights", "a1", days_ago=3, at=(8, 30), role_name="旧名"),
            _log(
                SklandCheckinLog,
                1,
                "arknights",
                "a1",
                days_ago=1,
                at=(8, 31),
                role_name="白衣",
                channel_name="官服",
            ),
            _log(
                SklandCheckinLog,
                1,
                "arknights",
                "a1",
                days_ago=0,
                at=(6, 0),
                source="status",
                status="already",
                role_name="白衣#5820",
                channel_name="官服",
            ),
            _log(
                SklandCheckinLog,
                1,
                "endfield",
                "e1",
                days_ago=1,
                at=(9, 0),
                source="status",
                status="pending",
                role_name="管理员",
            ),
            _log(SklandCheckinLog, 2, "arknights", "b1", days_ago=2, at=(9, 0)),
            _log(SklandCheckinLog, 2, "endfield", "b2", days_ago=1, at=(7, 0)),
            _log(
                TaygedoCheckinLog,
                1,
                "app",
                "u1",
                days_ago=0,
                at=(7, 30),
                awards_text="金币x10",
                awards=[{"name": "金币", "count": 10}],
            ),
        ]
    )
    db.commit()


def _rows(page) -> list[tuple]:
    return [
        (t.task_key, t.user_label, t.included, t.auto_checkin, t.checkin_hour, t.checkin_minute)
        for t in page.items
    ]


def test_tasks_one_row_per_role_or_one_per_platform_without_prefs(db) -> None:
    _seed(db)
    page = query_user_checkin_tasks(db, page=1, page_size=100)

    assert page.total == 7
    assert _rows(page) == [
        ("skland:1:arknights:a0", "Alice", False, False, 8, 0),
        ("skland:1:arknights:a1", "Alice", True, True, 8, 30),
        ("skland:1:endfield:e1", "Alice", True, False, 9, 0),
        ("skland:2", "m2", True, True, 5, 5),
        ("taygedo:1:app:u1", "Alice", True, True, 7, 30),
        ("taygedo:1:1289:r1", "Alice", True, True, 7, 0),
        ("taygedo:3:app:u3", "Bob", True, False, 0, 0),
    ]
    by_key = {t.task_key: t for t in page.items}

    a1 = by_key["skland:1:arknights:a1"]
    assert (a1.game_name, a1.role_name, a1.channel_name) == ("arknights-name", "白衣#5820", "官服")
    assert (a1.today_status, a1.today_status_label) == ("already", "已签")
    assert a1.last_checkin_at == _fmt(_at(1, 8, 31))
    assert a1.last_checkin_date == (today() - timedelta(days=1)).isoformat()
    assert a1.bound_at == "2026-01-01 10:00:00"

    e1 = by_key["skland:1:endfield:e1"]
    assert (e1.game_name, e1.role_name, e1.channel_name) == ("endfield", "e1", None)
    assert (e1.today_status, e1.last_checkin_at, e1.last_checkin_date) == (None, None, None)

    whole = by_key["skland:2"]
    assert (whole.game_code, whole.role_uid, whole.today_status) == (None, None, None)
    assert whole.last_checkin_at == _fmt(_at(1, 7, 0))
    assert whole.last_checkin_date == (today() - timedelta(days=1)).isoformat()

    u1 = by_key["taygedo:1:app:u1"]
    assert (u1.today_status, u1.today_status_label) == ("ok", "已签")
    assert [(a.name, a.count) for a in u1.today_awards] == [("金币", 10)]
    assert u1.today_awards_text
    assert u1.last_checkin_at == _fmt(_at(0, 7, 30))


def test_tasks_filter_by_member_and_platform(db) -> None:
    _seed(db)
    mine = query_user_checkin_tasks(db, member_id=1, page=1, page_size=100)
    assert [t.task_key for t in mine.items] == [
        "skland:1:arknights:a0",
        "skland:1:arknights:a1",
        "skland:1:endfield:e1",
        "taygedo:1:app:u1",
        "taygedo:1:1289:r1",
    ]
    taygedo = query_user_checkin_tasks(db, platform="taygedo", page=1, page_size=100)
    assert [t.task_key for t in taygedo.items] == [
        "taygedo:1:app:u1",
        "taygedo:1:1289:r1",
        "taygedo:3:app:u3",
    ]
    with pytest.raises(HTTPException):
        query_user_checkin_tasks(db, platform="steam")


def test_tasks_pages_concatenate_to_the_full_list(db) -> None:
    _seed(db)
    full = query_user_checkin_tasks(db, page=1, page_size=100)
    pages = [query_user_checkin_tasks(db, page=n, page_size=3) for n in (1, 2, 3, 4)]

    assert [p.total for p in pages] == [7, 7, 7, 7]
    assert [len(p.items) for p in pages] == [3, 3, 1, 0]
    assert [t.model_dump() for p in pages for t in p.items] == [
        t.model_dump() for t in full.items
    ]


def _seed_members(db, count: int) -> None:
    for member_id in range(1, count + 1):
        _member(db, member_id, user=f"U{member_id}")
        db.add(SklandBind(id=member_id, member_id=member_id, token_enc="x"))
        db.add(TaygedoBind(id=member_id, member_id=member_id, credentials_enc="x"))
        db.add(_pref("skland", member_id, "arknights", f"a{member_id}"))
        db.add(_log(SklandCheckinLog, member_id, "arknights", f"a{member_id}", days_ago=1, at=(8, 0)))
        db.add(_log(SklandCheckinLog, member_id, "arknights", f"a{member_id}", days_ago=0, at=(8, 0)))
    db.commit()


def _count_selects(engine, call) -> int:
    seen: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return len(seen)


def test_task_list_query_count_does_not_grow_with_members(engine) -> None:
    def _selects(count: int) -> int:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine, autoflush=False)()
        try:
            _seed_members(session, count)
            page = None

            def _call() -> None:
                nonlocal page
                page = query_user_checkin_tasks(session, page=1, page_size=500)

            n = _count_selects(engine, _call)
            assert page is not None and page.total == 2 * count
            assert all(t.last_checkin_at for t in page.items if t.platform == "skland")
            return n
        finally:
            session.close()

    assert _selects(2) == _selects(12)


def test_last_checkin_is_found_behind_many_newer_logs_of_other_roles(db) -> None:
    _member(db, 1)
    db.add(SklandBind(id=1, member_id=1, token_enc="x"))
    db.add(_log(SklandCheckinLog, 1, "arknights", "quiet", days_ago=100, at=(8, 0)))
    for days_ago in range(1, 91):
        db.add(_log(SklandCheckinLog, 1, "arknights", "busy", days_ago=days_ago, at=(8, 0)))
    db.add(_log(SklandCheckinLog, 1, "arknights", "busy", days_ago=0, at=(9, 0), source="status"))
    db.commit()

    out = attach_last_checkin_to_result_dicts(
        db,
        platform="skland",
        member_id=1,
        results=[
            {"game_code": "arknights", "role_uid": "quiet", "status": "pending"},
            {"game_code": "arknights", "role_uid": "busy", "status": "ok"},
            {"game_code": "arknights", "role_uid": "never", "status": "pending"},
        ],
    )
    assert [(r["role_uid"], r["last_checkin_date"]) for r in out] == [
        ("quiet", (today() - timedelta(days=100)).isoformat()),
        ("busy", (today() - timedelta(days=1)).isoformat()),
        ("never", None),
    ]
    assert out[1]["last_checkin_at"] == _fmt(_at(1, 8, 0))
    assert out[0]["status"] == "pending"
