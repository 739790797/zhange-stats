"""管理端角色级同步 trigger：带回上游 HTTP 原文。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.jobs.trigger_runs import (
    _checkin_adapter_for_job,
    _run_sync_role_checkin,
    get_job_run_events,
    list_job_runs,
    trigger_scheduled_job,
)
from app.api.jobs.schemas import JobTriggerRequest
from app.services.checkin.registry import get_checkin_adapters
from app.services.skland.checkin import skland_adapter
from app.services.skland.client import SklandApiError
from app.models.job_run import JobRun


def _member_db(member_id: int | None = 1) -> MagicMock:
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=member_id) if member_id else None
    return db


def test_every_checkin_job_resolves_its_adapter() -> None:
    for adapter in get_checkin_adapters().values():
        assert _checkin_adapter_for_job(adapter.job_key) is adapter
    assert _checkin_adapter_for_job("arknights_box_sync") is None


def test_sync_role_checkin_returns_exchanges(monkeypatch) -> None:
    bind = SimpleNamespace(member_id=1, id=5)
    db = _member_db()
    monkeypatch.setattr(skland_adapter, "get_bind", lambda _db, mid: bind if mid == 1 else None)

    def _fake_run(adapter, db_arg, bind_arg, *, force, role_keys):
        assert adapter is skland_adapter
        assert bind_arg is bind
        assert force is True
        assert role_keys == {("arknights", "uid-1")}
        return {
            "ok": True,
            "summary": "签到成功",
            "results": [],
            "exchanges": [
                {
                    "game_code": "arknights",
                    "role_uid": "uid-1",
                    "status": "ok",
                    "upstream_request": "POST https://zonai.skland.com/api/v1/game/attendance\n{}",
                    "upstream_response": '{"code":0,"data":{}}',
                }
            ],
        }

    monkeypatch.setattr("app.api.jobs.trigger_runs.run_checkin_for_bind", _fake_run)

    out = _run_sync_role_checkin(
        db,
        job_id="skland_checkin",
        member_id=1,
        game_code="arknights",
        role_uid="uid-1",
    )
    assert out["ok"] is True
    assert out["exchanges"][0]["upstream_response"] == '{"code":0,"data":{}}'


def _sync_error(db, job_id: str = "skland_checkin") -> HTTPException:
    with pytest.raises(HTTPException) as ei:
        _run_sync_role_checkin(
            db, job_id=job_id, member_id=1, game_code="arknights", role_uid="u1"
        )
    return ei.value


def test_sync_role_checkin_rejects_missing_member_before_job() -> None:
    err = _sync_error(_member_db(None), job_id="arknights_box_sync")
    assert (err.status_code, err.detail) == (404, "用户不存在")


def test_sync_role_checkin_rejects_non_checkin_job() -> None:
    err = _sync_error(_member_db(), job_id="arknights_box_sync")
    assert err.status_code == 400


def test_sync_role_checkin_reports_unbound_platform(monkeypatch) -> None:
    monkeypatch.setattr(skland_adapter, "get_bind", lambda _db, _mid: None)
    err = _sync_error(_member_db())
    assert (err.status_code, err.detail) == (400, "该用户尚未绑定森空岛")


def test_sync_role_checkin_maps_upstream_error_to_400(monkeypatch) -> None:
    monkeypatch.setattr(
        skland_adapter, "get_bind", lambda _db, _mid: SimpleNamespace(member_id=1, id=5)
    )

    def _fail(*_a, **_k):
        raise SklandApiError("凭证可能已失效，请重新绑定森空岛（用户未登录）")

    monkeypatch.setattr("app.api.jobs.trigger_runs.run_checkin_for_bind", _fail)
    err = _sync_error(_member_db())
    assert err.status_code == 400
    assert "请重新绑定森空岛" in err.detail


def test_trigger_role_sync_short_circuits(monkeypatch) -> None:
    db = MagicMock()

    monkeypatch.setattr(
        "app.api.jobs.trigger_runs._run_sync_role_checkin",
        lambda *a, **k: {
            "ok": True,
            "summary": "完成",
            "exchanges": [
                {
                    "game_code": "arknights",
                    "role_uid": "u1",
                    "status": "ok",
                    "upstream_request": "POST /x",
                    "upstream_response": '{"code":0}',
                }
            ],
        },
    )
    # 避免走异步路径的依赖
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.try_acquire_manual_trigger",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not async")),
    )

    result = trigger_scheduled_job(
        "skland_checkin",
        JobTriggerRequest(member_id=1, game_code="arknights", role_uid="u1"),
        db=db,
        _=SimpleNamespace(id=1, role="admin"),
    )
    assert result.accepted is True
    assert result.ok is True
    assert result.exchanges
    assert result.exchanges[0].upstream_response == '{"code":0}'


def test_sync_trigger_returns_server_run_id_and_category(monkeypatch) -> None:
    db = MagicMock()
    calls: list[tuple[str, int]] = []
    completion: list[object] = []

    monkeypatch.setattr("app.api.jobs.trigger_runs._job_has_running_run", lambda *_: False)
    monkeypatch.setattr("app.api.jobs.trigger_runs.try_acquire_manual_trigger", lambda *_: True)
    monkeypatch.setattr("app.api.jobs.trigger_runs.release_manual_trigger", lambda *_: None)
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.resolve_sync_job_handler",
        lambda *_a, **_k: lambda: None,
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.create_queued_job_run",
        lambda *_a, **_k: SimpleNamespace(id=77),
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.launch_sync_job_process",
        lambda job_id, run_id, *, on_finish: (
            calls.append((job_id, run_id)), completion.append(on_finish)
        ),
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.release_manual_trigger",
        lambda job_id: calls.append(("released", 77)),
    )

    result = trigger_scheduled_job(
        "endfield_repo_sync",
        None,
        db=db,
        _=SimpleNamespace(id=1, role="admin"),
    )
    assert result.run_id == 77
    assert result.category == "repository"
    assert calls == [("endfield_repo_sync", 77)]
    completion[0]()
    assert calls[-1] == ("released", 77)


def test_trigger_role_requires_full_keys() -> None:
    with pytest.raises(HTTPException) as ei:
        trigger_scheduled_job(
            "skland_checkin",
            JobTriggerRequest(member_id=1, game_code="arknights"),
            db=MagicMock(),
            _=SimpleNamespace(id=1, role="admin"),
        )
    assert ei.value.status_code == 400


def test_sync_trigger_marks_run_failed_when_child_cannot_start(monkeypatch) -> None:
    writes: list[dict[str, object]] = []
    releases: list[str] = []
    monkeypatch.setattr("app.api.jobs.trigger_runs._job_has_running_run", lambda *_: False)
    monkeypatch.setattr("app.api.jobs.trigger_runs.try_acquire_manual_trigger", lambda *_: True)
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.release_manual_trigger", lambda job_id: releases.append(job_id)
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.resolve_sync_job_handler", lambda *_a, **_k: lambda: None
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.create_queued_job_run",
        lambda *_a, **_k: SimpleNamespace(id=81),
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.launch_sync_job_process",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("spawn failed")),
    )
    monkeypatch.setattr(
        "app.api.jobs.trigger_runs.write_job_run",
        lambda run_id, job_id, **kwargs: writes.append(
            {"run_id": run_id, "job_id": job_id, **kwargs}
        ),
    )

    with pytest.raises(HTTPException) as error:
        trigger_scheduled_job(
            "endfield_repo_sync",
            None,
            db=MagicMock(),
            _=SimpleNamespace(id=1, role="admin"),
        )

    assert error.value.status_code == 500
    assert writes[0]["run_id"] == 81
    assert writes[0]["status"] == "error"
    assert releases == ["endfield_repo_sync"]


def test_job_run_query_can_return_exact_run_id() -> None:
    engine = create_engine("sqlite:///:memory:")
    JobRun.__table__.create(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            JobRun(job_key="endfield_repo_sync", status="ok", message="old"),
            JobRun(job_key="endfield_repo_sync", status="queued", message="new"),
        ]
    )
    db.commit()
    wanted = db.query(JobRun).filter_by(message="new").one()

    page = list_job_runs(
        "endfield_repo_sync",
        run_id=wanted.id,
        page=1,
        page_size=20,
        db=db,
        _=SimpleNamespace(id=1, role="admin"),
    )

    assert page.total == 1
    assert [row.id for row in page.items] == [wanted.id]
    assert page.items[0].status == "queued"
    db.close()
    engine.dispose()


def test_job_run_events_returns_incremental_logs(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    JobRun.__table__.create(bind=engine)
    db = sessionmaker(bind=engine)()
    run = JobRun(job_key="endfield_repo_sync", status="running", message="正在同步")
    db.add(run)
    db.commit()
    db.refresh(run)
    seen: list[tuple[int, int]] = []

    def _logs(run_id: int, *, after_id: int, limit: int):
        seen.append((run_id, after_id))
        return [
            SimpleNamespace(
                id=5,
                created_at=None,
                level="INFO",
                logger="sync",
                message="同步中",
                is_truncation=False,
            ),
            SimpleNamespace(
                id=6,
                created_at=None,
                level="WARNING",
                logger="sync",
                message="部分跳过",
                is_truncation=False,
            ),
        ][:limit]

    monkeypatch.setattr("app.api.jobs.trigger_runs.list_job_run_logs", _logs)
    response = get_job_run_events(
        "endfield_repo_sync",
        run.id,
        after_id=4,
        limit=1,
        db=db,
        _=SimpleNamespace(id=1, role="admin"),
    )
    assert seen == [(run.id, 4)]
    assert [item.id for item in response.logs] == [5]
    assert response.next_after_id == 5
    assert response.has_more is True
    db.close()
    engine.dispose()
