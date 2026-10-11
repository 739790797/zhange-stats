"""管理端角色级同步 trigger：带回上游 HTTP 原文。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
import pytest

from app.api.jobs.trigger_runs import (
    _checkin_adapter_for_job,
    _run_sync_role_checkin,
    trigger_scheduled_job,
)
from app.api.jobs.schemas import JobTriggerRequest
from app.services.checkin.registry import get_checkin_adapters
from app.services.skland.checkin import skland_adapter
from app.services.skland.client import SklandApiError


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


def test_trigger_role_requires_full_keys() -> None:
    with pytest.raises(HTTPException) as ei:
        trigger_scheduled_job(
            "skland_checkin",
            JobTriggerRequest(member_id=1, game_code="arknights"),
            db=MagicMock(),
            _=SimpleNamespace(id=1, role="admin"),
        )
    assert ei.value.status_code == 400
