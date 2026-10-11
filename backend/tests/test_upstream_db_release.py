"""打上游（换票、拉角色、拉日历、扫码轮询）时不占着数据库连接：先结束事务再发请求。"""

from __future__ import annotations

import importlib
import time
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import crypto_secret
from app.core.crypto_secret import encrypt_secret
from app.core.database import Base
from app.models.member import Member
from app.models.skland import SklandBind
from app.services.checkin.common import CheckinResult
from app.services.skland import checkin as skland_checkin
from app.services.skland.client import SklandRole, SklandSession

_ROLE = SklandRole(
    game_code="arknights",
    game_name="明日方舟",
    uid="u1",
    role_name="博士",
    channel_name="官服",
    channel_master_id="1",
)


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    holder = SimpleNamespace(SECRET_KEY="unit-test-secret-key-0123456789abcdef")
    monkeypatch.setattr(crypto_secret, "get_settings", lambda: holder)


@pytest.fixture
def db_member():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    member = Member(id=7, nickname="m7")
    db.add(member)
    db.add(SklandBind(member_id=7, token_enc=encrypt_secret("hg-token"), auto_checkin=False))
    db.commit()
    yield db, member
    db.close()


@pytest.fixture
def upstream(monkeypatch, db_member) -> list[tuple[str, bool]]:
    """森空岛上游桩：记下每次调用时 Session 是否还开着事务（开着就占着池里的连接）。"""
    db, _ = db_member
    calls: list[tuple[str, bool]] = []
    session = SklandSession(cred="cred", sign_token="sign")

    def stub(name: str, result: Any):
        def call(*_args, **_kwargs):
            calls.append((name, db.in_transaction()))
            return result

        return call

    today = CheckinResult(
        game_code=_ROLE.game_code,
        game_name=_ROLE.game_name,
        role_uid=_ROLE.uid,
        role_name=_ROLE.role_name,
        channel_name=_ROLE.channel_name,
        status="already",
        message="",
    )
    monkeypatch.setattr(
        "app.services.skland.session_cache.get_cached_skland_session", lambda *_a: None
    )
    monkeypatch.setattr(
        "app.services.skland.session_cache.put_cached_skland_session", lambda *_a: None
    )
    monkeypatch.setattr(skland_checkin, "login_with_token", stub("login", session))
    monkeypatch.setattr(skland_checkin, "list_roles", stub("list_roles", [_ROLE]))
    monkeypatch.setattr(
        skland_checkin, "skland_query_today_all", stub("query_today", (session, [today]))
    )
    monkeypatch.setattr(
        skland_checkin, "fetch_arknights_attendance", stub("fetch_calendar", {"calendar": []})
    )
    monkeypatch.setattr(
        skland_checkin,
        "parse_arknights_attendance_calendar",
        lambda *_a, **_k: {"days": []},
    )
    return calls


def test_skland_preview_roles_holds_no_transaction_upstream(db_member, upstream) -> None:
    db, member = db_member
    assert skland_checkin.preview_roles(db, member) == [_ROLE]
    assert upstream == [("login", False), ("list_roles", False)]


def test_skland_calendar_refresh_releases_connection_before_each_upstream_call(
    db_member, upstream
) -> None:
    db, member = db_member
    _parsed, role, roles, synced_at, stale = (
        skland_checkin.get_arknights_attendance_calendar_for_member(db, member, force=True)
    )
    # 拉完角色后还查了一次 raw 表，再拉日历前要重新交还连接
    assert upstream == [("login", False), ("list_roles", False), ("fetch_calendar", False)]
    assert role.uid == "u1" and roles == [_ROLE]
    assert synced_at is not None and stale is False


def test_skland_status_query_logs_in_without_open_transaction(db_member, upstream) -> None:
    db, _member = db_member
    bind = skland_checkin.get_bind_for_member(db, 7)
    out = skland_checkin.query_today_for_bind(db, bind, force=True)
    assert upstream == [("login", False), ("query_today", False)]
    assert [r["status"] for r in out["results"]] == ["already"]


@pytest.mark.parametrize(
    ("module", "poll_fn", "poll_result"),
    [
        (
            "app.services.skland.qr",
            "poll_scan_status",
            SimpleNamespace(status="waiting", message="等待扫码", scan_code=None),
        ),
        ("app.services.mihoyo.qr", "query_qr_login", {"status": "waiting", "message": "等待扫码"}),
    ],
)
def test_qr_poll_releases_connection_before_asking_upstream(
    monkeypatch, db_member, module, poll_fn, poll_result
) -> None:
    db, _ = db_member
    qr = importlib.import_module(module)
    scan_id = f"scan-{uuid.uuid4().hex}"
    member = db.get(Member, 7)
    assert db.in_transaction()
    qr._save_pending(
        scan_id,
        {"user_id": 11, "member_id": 7, "device_id": "dev", "created_at": time.time()},
    )
    seen: list[bool] = []

    def poll(*_args, **_kwargs):
        seen.append(db.in_transaction())
        return poll_result

    monkeypatch.setattr(qr, poll_fn, poll)
    out = qr.poll_qr_bind(db, user_id=11, member=member, scan_id=scan_id)
    assert out["status"] == "waiting"
    assert seen == [False]
