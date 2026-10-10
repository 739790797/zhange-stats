"""塔科夫回源单飞：整站同步、单栏目回源与冷启动 ensure_* 共用一把锁；管理端整站同步转后台。"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.guides import tarkov as tarkov_api
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.job_run import JobRun
from app.models.user import User, UserRole
from app.services.tarkov import items as items_svc
from app.services.tarkov import sync as full_sync
from app.services.tarkov import sync_lock
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov.game_mode import run_for_modes


def _lock_free() -> bool:
    if not sync_lock._lock.acquire(blocking=False):
        return False
    sync_lock._lock.release()
    return True


def _wait_until(pred, timeout: float = 5.0) -> bool:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return bool(pred())


@pytest.fixture(autouse=True)
def _sync_lock_left_free():
    yield
    full_sync._full_sync_active.clear()
    leaked = not _lock_free()
    if leaked:
        sync_lock._lock.release()
    assert not leaked, "用例结束时回源锁仍被占着"


class _Boom(Exception):
    pass


def test_claim_blocks_others_until_unclaim() -> None:
    sync_lock.claim()
    try:
        with pytest.raises(sync_lock.TarkovSyncBusy) as busy:
            sync_lock.claim()
        assert busy.value.message == sync_lock.BUSY_MESSAGE
        with pytest.raises(sync_lock.TarkovSyncBusy):
            with sync_lock.exclusive():
                pass
    finally:
        sync_lock.unclaim()
    with sync_lock.exclusive():
        pass


def test_exclusive_reenters_for_owner_and_releases_on_error() -> None:
    with pytest.raises(_Boom):
        with sync_lock.exclusive():
            with sync_lock.cold_start():
                with sync_lock.exclusive():
                    assert sync_lock._owned()
            raise _Boom()
    assert not sync_lock._owned()
    assert _lock_free()


def test_held_hands_claimed_lock_to_worker_thread() -> None:
    sync_lock.claim()
    seen: dict[str, bool] = {}

    def worker() -> None:
        with sync_lock.held():
            seen["owner"] = sync_lock._owned()
            with sync_lock.exclusive():
                seen["reentered"] = True

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(5)
    assert seen == {"owner": True, "reentered": True}
    assert not sync_lock._owned()
    assert _lock_free()


def test_cold_start_waits_briefly_then_busy(monkeypatch) -> None:
    monkeypatch.setattr(sync_lock, "COLD_START_WAIT_SEC", 0.05)
    sync_lock.claim()
    try:
        started = time.monotonic()
        with pytest.raises(sync_lock.TarkovSyncBusy):
            with sync_lock.cold_start():
                pass
        assert time.monotonic() - started >= 0.04
    finally:
        sync_lock.unclaim()


class _CommitCounter:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def test_fill_once_skips_lock_when_data_present() -> None:
    db = _CommitCounter()
    fills: list[int] = []
    sync_lock.claim()
    try:
        sync_lock.fill_once(db, lambda: False, lambda: fills.append(1))
    finally:
        sync_lock.unclaim()
    assert fills == []
    assert db.commits == 0


def test_fill_once_rechecks_after_lock_and_skips_duplicate_sync() -> None:
    db = _CommitCounter()
    answers = iter([True, False])
    fills: list[int] = []
    sync_lock.fill_once(db, lambda: next(answers), lambda: fills.append(1))
    assert fills == []
    assert db.commits == 1


def test_fill_once_fills_under_lock_when_still_missing() -> None:
    db = _CommitCounter()
    owned: list[bool] = []
    sync_lock.fill_once(db, lambda: True, lambda: owned.append(sync_lock._owned()))
    assert owned == [True]
    assert db.commits == 1
    assert _lock_free()


def test_domain_sync_is_busy_while_other_sync_holds_lock() -> None:
    calls: list[str] = []
    sync_lock.claim()
    try:
        with pytest.raises(sync_lock.TarkovSyncBusy):
            run_for_modes(
                lambda: calls.append("ran"),
                game_mode="pvp",
                error_cls=_Boom,
                label="测试",
            )
    finally:
        sync_lock.unclaim()
    assert calls == []


def test_domain_sync_inside_cold_start_reuses_lock() -> None:
    with sync_lock.cold_start():
        out = run_for_modes(lambda: "ok", error_cls=_Boom, label="测试")
    assert out == "ok"
    assert _lock_free()


def test_admin_full_sync_runs_in_background_and_frees_lock(monkeypatch) -> None:
    release = threading.Event()
    seen: dict[str, object] = {}
    created: list[int] = []

    def fake_run(run_id: int) -> None:
        seen.update(
            run_id=run_id,
            owner=sync_lock._owned(),
            thread=threading.current_thread().name,
        )
        release.wait(5)

    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: created.append(1) or 41)
    monkeypatch.setattr(full_sync, "_run_full_sync", fake_run)

    assert full_sync.start_full_sync() == 41
    try:
        assert _wait_until(lambda: "run_id" in seen)
        with pytest.raises(sync_lock.TarkovSyncBusy):
            full_sync.start_full_sync()
        with pytest.raises(sync_lock.TarkovSyncBusy):
            items_svc.sync_from_upstream(None)  # type: ignore[arg-type]
        full_sync.full_sync_job_wrapper()
    finally:
        release.set()
    assert _wait_until(lambda: not full_sync._full_sync_active.is_set())
    assert seen == {"run_id": 41, "owner": True, "thread": "tarkov-full-sync"}
    assert created == [1]
    assert _lock_free()


def test_admin_full_sync_frees_lock_when_run_row_fails(monkeypatch) -> None:
    def no_db() -> int:
        raise RuntimeError("db down")

    monkeypatch.setattr(full_sync, "_create_full_sync_run", no_db)
    with pytest.raises(RuntimeError):
        full_sync.start_full_sync()
    assert not full_sync._full_sync_active.is_set()
    assert _lock_free()


def test_cron_full_sync_runs_under_lock(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(run_id: int) -> None:
        seen.update(
            run_id=run_id,
            owner=sync_lock._owned(),
            active=full_sync._full_sync_active.is_set(),
        )

    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: 5)
    monkeypatch.setattr(full_sync, "_run_full_sync", fake_run)
    full_sync.full_sync_job_wrapper()
    assert seen == {"run_id": 5, "owner": True, "active": True}
    assert not full_sync._full_sync_active.is_set()
    assert _lock_free()


def test_cron_skips_while_full_sync_active(monkeypatch) -> None:
    created: list[int] = []
    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: created.append(1) or 1)
    full_sync._full_sync_active.set()
    full_sync.full_sync_job_wrapper()
    assert created == []


def test_cron_skips_when_full_sync_ran_while_waiting(monkeypatch) -> None:
    created: list[int] = []
    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: created.append(1) or 1)
    real_exclusive = sync_lock.exclusive

    @contextmanager
    def exclusive_after_other_full_sync(*, wait: float = 0.0):
        time.sleep(0.001)
        full_sync._begin_full_sync()
        full_sync._full_sync_active.clear()
        with real_exclusive(wait=wait):
            yield

    monkeypatch.setattr(sync_lock, "exclusive", exclusive_after_other_full_sync)
    full_sync.full_sync_job_wrapper()
    assert created == []


def test_cron_gives_up_when_lock_stays_busy(monkeypatch, caplog) -> None:
    monkeypatch.setattr(full_sync, "FULL_SYNC_LOCK_WAIT_SEC", 0.05)
    created: list[int] = []
    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: created.append(1) or 1)
    caplog.set_level(logging.WARNING, logger=full_sync.logger.name)
    sync_lock.claim()
    try:
        full_sync.full_sync_job_wrapper()
    finally:
        sync_lock.unclaim()
    assert created == []
    assert any("sync lock still busy" in rec.getMessage() for rec in caplog.records)


@pytest.fixture
def job_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    JobRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr("app.core.database.SessionLocal", factory)
    return factory


def test_full_sync_run_records_progress_and_result(job_db, monkeypatch) -> None:
    progress_seen: list[str] = []

    def fake_sync(db, *, progress=None, **_k):  # noqa: ANN001
        progress("正在下载 items（1/2）", {"phase": "download", "percent": 10, "domains": []})
        with job_db() as check:
            progress_seen.append(check.get(JobRun, run_id).message or "")
        return {
            "ok_count": 1,
            "failed_count": 0,
            "domains": [{"id": "items", "ok": True, "status": "ok", "mode": "pvp"}],
            "message": "ok",
        }

    monkeypatch.setattr(full_sync, "sync_all_from_upstream", fake_sync)
    run_id = full_sync._create_full_sync_run()
    with job_db() as db:
        row = db.get(JobRun, run_id)
        assert row.job_key == full_sync.FULL_SYNC_JOB_KEY
        assert row.status == "running"
        assert row.stats["domains"]
    full_sync._run_full_sync(run_id)
    assert progress_seen == ["正在下载 items（1/2）"]
    with job_db() as db:
        row = db.get(JobRun, run_id)
        assert row.status == "ok"
        assert row.finished_at is not None
        assert row.stats["percent"] == 100
        assert json.loads(row.message)["ok_count"] == 1


def test_full_sync_run_marks_error_without_raising(job_db, monkeypatch) -> None:
    def boom(db, **_k):  # noqa: ANN001
        raise full_sync.TarkovFullSyncError("全量同步失败：dump: down")

    monkeypatch.setattr(full_sync, "sync_all_from_upstream", boom)
    run_id = full_sync._create_full_sync_run()
    full_sync._run_full_sync(run_id)
    with job_db() as db:
        row = db.get(JobRun, run_id)
        assert row.status == "error"
        assert row.finished_at is not None
        assert "dump: down" in (row.message or "")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.core.platform_deps.is_feature_enabled", lambda _db, _feature: True)
    admin = User(
        id=1,
        username="admin",
        display_name="管理员",
        password_hash="x",
        role=UserRole.admin,
    )
    app = FastAPI()
    app.include_router(tarkov_api.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_admin] = lambda: admin
    with TestClient(app) as tc:
        yield tc


def test_cold_start_busy_is_503_with_retry_after(client, monkeypatch) -> None:
    monkeypatch.setattr(sync_lock, "COLD_START_WAIT_SEC", 0.05)
    monkeypatch.setattr(items_svc, "get_items_raw", lambda _db: None)
    synced: list[int] = []
    monkeypatch.setattr(items_svc, "sync_from_upstream", lambda *_a, **_k: synced.append(1))
    sync_lock.claim()
    try:
        resp = client.get("/tarkov/ammo")
    finally:
        sync_lock.unclaim()
    assert resp.status_code == 503
    assert resp.json() == {"detail": sync_lock.BUSY_MESSAGE}
    assert resp.headers["retry-after"] == str(tarkov_api.SYNC_BUSY_RETRY_AFTER_SEC)
    assert synced == []


def test_admin_full_sync_returns_202_and_run_id(client, monkeypatch) -> None:
    done = threading.Event()
    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: 9)
    monkeypatch.setattr(full_sync, "_run_full_sync", lambda _rid: done.set())
    resp = client.post("/tarkov/sync")
    assert resp.status_code == 202
    assert resp.json() == {
        "accepted": True,
        "job_id": full_sync.FULL_SYNC_JOB_KEY,
        "run_id": 9,
        "status": "running",
        "message": full_sync.FULL_SYNC_STARTED_MESSAGE,
    }
    assert done.wait(5)
    assert _wait_until(lambda: not full_sync._full_sync_active.is_set())


@pytest.mark.parametrize(
    "path",
    [
        "/tarkov/sync",
        "/tarkov/items/sync",
        "/tarkov/tasks/sync",
        "/tarkov/traders/sync",
        "/tarkov/bosses/sync",
        "/tarkov/guides/sync",
    ],
)
def test_admin_sync_conflicts_while_lock_held(client, monkeypatch, path) -> None:
    created: list[int] = []
    monkeypatch.setattr(full_sync, "_create_full_sync_run", lambda: created.append(1) or 1)
    sync_lock.claim()
    try:
        resp = client.post(path)
    finally:
        sync_lock.unclaim()
    assert resp.status_code == 409
    assert resp.json()["detail"] == sync_lock.BUSY_MESSAGE
    assert created == []


def test_domain_sync_route_runs_when_lock_free(client, monkeypatch) -> None:
    owned: list[bool] = []

    def fake_sync(_db) -> dict:  # noqa: ANN001
        owned.append(sync_lock._owned())
        return {"task_count": 3, "source": "json", "synced_at": "t"}

    monkeypatch.setattr(
        tasks_svc,
        "_sync_current_mode",
        lambda db: fake_sync(db),
    )
    resp = client.post("/tarkov/tasks/sync")
    assert resp.status_code == 200
    assert resp.json()["task_count"] == 3
    assert owned == [True, True]
    assert _lock_free()
