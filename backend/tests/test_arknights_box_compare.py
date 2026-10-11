"""明日方舟盒子对比：别人的盒子只读快照，不拿对方森空岛凭证回源；uid 按已同步角色校验。"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.biz_logging import clear_log_until_change
from app.core.database import Base
from app.core.timeutil import now_naive, today
from app.models.arknights import ArknightsBoxSnapshot
from app.models.member import Member
from app.models.skland import SklandAttendanceRaw, SklandBind
from app.models.user import User, UserRole
from app.services.skland import arknights_box_compare as compare
from app.services.skland.client import SklandApiError


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    monkeypatch.setattr(compare, "ensure_catalog", lambda _db: [])
    monkeypatch.setattr(compare, "get_catalog_meta", lambda _db: None)
    clear_log_until_change()
    yield session
    session.close()
    engine.dispose()


def _member(db, name: str, *, bound: bool = True, persona: str | None = None) -> tuple[User, Member]:
    user = User(username=name, display_name=name, password_hash="x", role=UserRole.user)
    db.add(user)
    db.flush()
    member = Member(nickname=name, user_id=user.id, steam_persona_name=persona)
    db.add(member)
    db.flush()
    if bound:
        db.add(SklandBind(member_id=member.id, token_enc="enc"))
    db.commit()
    return user, member


def _snapshot(db, member_id: int, uid: str, *, days_ago: int = 0, roles=None) -> None:
    payload = {
        "status": "ok",
        "message": None,
        "uid": uid,
        "role_name": f"博士{uid}",
        "channel_name": "官服",
        "owned": {"char_002_amiya": {"level": 50, "evolve_phase": 2}},
        "char_count": 1,
        "roles": roles if roles is not None else [{"uid": uid, "role_name": f"博士{uid}", "channel_name": "官服"}],
    }
    db.add(
        ArknightsBoxSnapshot(
            member_id=member_id,
            uid=uid,
            payload_json=json.dumps(payload),
            sync_date=today() - timedelta(days=days_ago),
            synced_at=now_naive() - timedelta(days=days_ago),
        )
    )
    db.commit()


def _upstream(monkeypatch, *, fail: bool = False) -> list[int]:
    calls: list[int] = []

    def fake(_db, member, uid=None):
        calls.append(member.id)
        if fail:
            raise SklandApiError("森空岛暂时不可用")
        role = SimpleNamespace(uid="900", role_name="我", channel_name="官服")
        box = SimpleNamespace(uid="900", chars=[], char_count=0, name="我", level=120)
        return box, role, [role]

    monkeypatch.setattr(compare, "get_arknights_box_for_member", fake)
    return calls


def test_other_members_are_served_from_snapshots_only(db, monkeypatch) -> None:
    viewer, me = _member(db, "me")
    _user, other = _member(db, "other")
    _snapshot(db, other.id, "111", days_ago=3)
    calls = _upstream(monkeypatch)

    out = compare.build_box_compare(db, viewer, [me.id, other.id])

    assert calls == [me.id]
    rows = {r["member_id"]: r for r in out["rows"]}
    assert rows[other.id]["status"] == "ok"
    assert rows[other.id]["uid"] == "111"
    assert "char_002_amiya" in rows[other.id]["owned"]


def test_other_member_without_snapshot_uses_cached_roles(db, monkeypatch) -> None:
    viewer, me = _member(db, "me")
    _user, other = _member(db, "other")
    db.add(
        SklandAttendanceRaw(
            member_id=other.id,
            uid="222",
            role_name="别人",
            channel_name="B服",
            raw_json="{}",
            synced_at=now_naive(),
        )
    )
    db.commit()
    calls = _upstream(monkeypatch)

    out = compare.build_box_compare(db, viewer, [other.id])

    assert calls == []
    row = out["rows"][0]
    assert row["status"] == "no_snapshot"
    assert [r["uid"] for r in row["roles"]] == ["222"]


def test_other_member_uid_must_be_a_synced_role(db, monkeypatch) -> None:
    viewer, _me = _member(db, "me")
    _user, other = _member(db, "other")
    _snapshot(db, other.id, "111")
    calls = _upstream(monkeypatch)

    out = compare.build_box_compare(db, viewer, [other.id], role_uids={other.id: "999"})

    assert calls == []
    row = out["rows"][0]
    assert row["status"] == "error"
    assert row["owned"] == {}
    # 前端据此清掉记住的失效 uid
    assert [r["uid"] for r in row["roles"]] == ["111"]


def test_nicknames_drop_markup(db, monkeypatch) -> None:
    viewer, me = _member(db, "me", persona="<b>Dr</b>")
    _snapshot(db, me.id, "900")
    _upstream(monkeypatch)

    out = compare.build_box_compare(db, viewer, [me.id])
    assert out["rows"][0]["nickname"] == "bDr/b"
    assert compare.list_compare_candidates(db, viewer)[0]["nickname"] == "bDr/b"


def test_sync_job_reports_refresh_failure_instead_of_stale(db, monkeypatch, caplog) -> None:
    _viewer, me = _member(db, "me")
    _snapshot(db, me.id, "900", days_ago=2)
    _upstream(monkeypatch, fail=True)

    with caplog.at_level(logging.DEBUG, logger=compare.logger.name):
        first = compare.run_arknights_box_sync_job(db)
        second = compare.run_arknights_box_sync_job(db)

    assert first["failed"] == 1 and first["ok"] == 0
    assert second["failed"] == 1
    records = [r for r in caplog.records if "arknights box sync failed" in r.getMessage()]
    assert [r.levelno for r in records] == [logging.WARNING, logging.DEBUG]
    assert all(r.exc_info is None for r in records)


def _client(monkeypatch, db, viewer: User) -> TestClient:
    from app.api.skland import arknights as api
    from app.core import platform_deps
    from app.core.database import get_db
    from app.core.deps import get_current_user

    monkeypatch.setattr(platform_deps, "is_feature_enabled", lambda _db, _fid: True)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/skland")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: viewer
    return TestClient(app)


@pytest.mark.parametrize(
    "params",
    [
        {"member_ids": "1,abc"},
        {"member_ids": "1", "role_uids": "1"},
        {"member_ids": "1", "role_uids": "x:111"},
        {"member_ids": "1", "role_uids": "1:<script>"},
    ],
)
def test_compare_rejects_malformed_params(db, monkeypatch, params) -> None:
    viewer, _me = _member(db, "me")
    resp = _client(monkeypatch, db, viewer).get("/api/skland/arknights/box/compare", params=params)
    assert resp.status_code == 400, resp.text


def test_compare_params_are_length_capped(db, monkeypatch) -> None:
    viewer, _me = _member(db, "me")
    client = _client(monkeypatch, db, viewer)
    resp = client.get(
        "/api/skland/arknights/box/compare", params={"member_ids": ",".join(["1"] * 200)}
    )
    assert resp.status_code == 422


def test_compare_is_rate_limited_per_viewer(db, monkeypatch) -> None:
    viewer, me = _member(db, "me")
    _snapshot(db, me.id, "900")
    _upstream(monkeypatch)
    client = _client(monkeypatch, db, viewer)
    codes = [
        client.get("/api/skland/arknights/box/compare", params={"member_ids": str(me.id)}).status_code
        for _ in range(61)
    ]
    assert set(codes[:60]) == {200}
    assert codes[60] == 429
