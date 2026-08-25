"""管理端角色级同步 trigger：带回上游 HTTP 原文。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
import pytest

from app.api.jobs.trigger_runs import _run_sync_role_checkin, trigger_scheduled_job
from app.api.jobs.schemas import JobTriggerRequest


def test_sync_role_checkin_returns_exchanges(monkeypatch) -> None:
    member = SimpleNamespace(id=1)
    db = MagicMock()
    db.get.return_value = member

    def _fake_run(db_arg, member_arg, *, force, role_keys):
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

    monkeypatch.setattr(
        "app.services.skland.checkin.run_checkin_for_member",
        _fake_run,
    )

    out = _run_sync_role_checkin(
        db,
        job_id="skland_checkin",
        member_id=1,
        game_code="arknights",
        role_uid="uid-1",
    )
    assert out["ok"] is True
    assert out["exchanges"][0]["upstream_response"] == '{"code":0,"data":{}}'


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
