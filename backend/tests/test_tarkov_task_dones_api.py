"""任务进度账接口：单任务 / 小步骤写入和批量写入一样，清空 / 转生之后不认旧 epoch。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.guides import tarkov as tarkov_api
from app.core import platform_deps
from app.core.database import Base, get_db
from app.core.security import create_user_access_token
from app.models.tarkov import TarkovUserTaskCleared, TarkovUserTaskDone
from app.models.user import User, UserRole

BASE = "/api/guides/tarkov/task-dones"


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    def _db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(platform_deps, "is_feature_enabled", lambda *_a: True)
    api = FastAPI()
    api.include_router(tarkov_api.router, prefix="/api/guides")
    api.dependency_overrides[get_db] = _db
    with SessionLocal() as db:
        user = User(
            username="alice",
            email="alice@example.com",
            display_name="alice",
            password_hash="unused",
            role=UserRole.user,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        token = create_user_access_token(user)
    client = TestClient(api)
    client.headers["Authorization"] = f"Bearer {token}"
    yield client, SessionLocal
    engine.dispose()


def _epoch(client) -> int:
    return client.get(BASE, params={"game_mode": "pvp"}).json()["reset_epoch"]


def test_single_task_writes_need_the_current_epoch_after_a_clear(ctx) -> None:
    client, SessionLocal = ctx
    pvp = {"game_mode": "pvp"}
    # 从没清空过：不带 epoch 照旧放行
    assert client.put(f"{BASE}/t1", params=pvp).status_code == 200
    assert client.post(f"{BASE}/clear", params=pvp).status_code == 200
    assert _epoch(client) == 1

    stale = {**pvp, "expect_epoch": 0}
    for method, path in (
        ("put", f"{BASE}/t1"),
        ("delete", f"{BASE}/t1"),
        ("put", f"{BASE}/t1/objectives/o1"),
        ("delete", f"{BASE}/t1/objectives/o1"),
    ):
        # 清空之前的旧页面：旧 epoch 与不带 epoch 都回 409，账上不留任何痕迹
        assert getattr(client, method)(path, params=stale).status_code == 409, path
        assert getattr(client, method)(path, params=pvp).status_code == 409, path
    with SessionLocal() as db:
        assert db.query(TarkovUserTaskDone).count() == 0
        assert db.query(TarkovUserTaskCleared).count() == 0

    fresh = {**pvp, "expect_epoch": 1}
    assert client.put(f"{BASE}/t1", params=fresh).status_code == 200
    assert client.delete(f"{BASE}/t1", params=fresh).status_code == 200
    with SessionLocal() as db:
        assert [row.task_id for row in db.query(TarkovUserTaskCleared)] == ["t1"]


def test_stale_bulk_write_leaves_no_partial_state(ctx) -> None:
    client, SessionLocal = ctx
    pvp = {"game_mode": "pvp"}
    assert client.post(f"{BASE}/clear", params=pvp).status_code == 200
    res = client.put(
        BASE, params=pvp, json={"task_ids": ["old"], "replace": False, "expect_epoch": 0}
    )
    assert res.status_code == 409
    with SessionLocal() as db:
        assert db.query(TarkovUserTaskDone).count() == 0


def test_reset_rejects_a_floor_in_the_future(ctx) -> None:
    client, _ = ctx
    res = client.post(
        f"{BASE}/reset",
        params={"game_mode": "pvp"},
        json={
            "reset_at": "2099-01-01 00:00:00",
            "profile_id": "aa11",
            "reason": "prestige",
            "expect_epoch": 0,
            "task_ids": [],
            "started_ids": [],
            "failed_ids": [],
            "objective_dones": [],
        },
    )
    assert res.status_code == 400
    assert _epoch(client) == 0


def test_contended_boundary_is_a_409_not_a_500(ctx, monkeypatch) -> None:
    """MariaDB 1020 / 1213：另一台设备正在清空同一账号。按过期账回 409，前端会重拉账号。"""
    from sqlalchemy.exc import OperationalError

    from app.services.tarkov import task_dones as dones

    client, _ = ctx

    class _Orig(Exception):
        pass

    def _boom(*_a, **_k):
        raise OperationalError("SELECT ...", {}, _Orig(1020, "Record has changed since last read"))

    monkeypatch.setattr(dones, "clear_progress", _boom)
    res = client.post(f"{BASE}/clear", params={"game_mode": "pvp"})
    assert res.status_code == 409

    def _other(*_a, **_k):
        raise OperationalError("SELECT ...", {}, _Orig(2006, "MySQL server has gone away"))

    monkeypatch.setattr(dones, "clear_progress", _other)
    with pytest.raises(OperationalError):
        client.post(f"{BASE}/clear", params={"game_mode": "pvp"})
