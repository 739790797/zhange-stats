"""签到编排 / Adapter 单测（假 Adapter，不打上游）。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from app.services.checkin_adapter import (
    CheckinAdapterBase,
    CheckinRunOutcome,
    SkipPolicy,
)
from app.services.checkin_common import CheckinResult
from app.services.checkin_orchestrator import (
    query_today_for_bind,
    run_checkin_for_bind,
)
from app.services.checkin_role_prefs import RoleKey


class _FakeApiError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _result(
    status: str = "ok",
    *,
    upstream_request: str | None = None,
    upstream_response: str | None = None,
) -> CheckinResult:
    return CheckinResult(
        game_code="g",
        game_name="G",
        role_uid="1",
        role_name="r",
        channel_name="c",
        status=status,
        message="m",
        awards_text="奖励×1",
        upstream_request=upstream_request,
        upstream_response=upstream_response,
    )


class _FakeAdapter(CheckinAdapterBase):
    platform = "fake"
    job_key = "fake_checkin"
    bind_model = SimpleNamespace
    log_model = SimpleNamespace
    api_error_cls = _FakeApiError
    empty_message = "空"
    skip_policy = SkipPolicy.LOGS_AUTHORITY

    def __init__(self) -> None:
        self.queries = 0
        self.runs = 0
        self.saved: list[Any] = []

    def get_bind(self, db, member_id: int):
        return None

    def load_session(self, db, bind):
        return {"token": "t"}

    def save_session(self, db, bind, session) -> None:
        self.saved.append(session)

    def query_today_all(self, session):
        self.queries += 1
        return session, [_result("already")]

    def run_checkins(
        self,
        session,
        *,
        force: bool,
        role_keys: set[RoleKey] | None,
    ) -> CheckinRunOutcome:
        self.runs += 1
        return CheckinRunOutcome(
            session=session,
            results=[
                _result(
                    "ok",
                    upstream_request="POST https://example.test/sign\n{}",
                    upstream_response='{"code":0}',
                )
            ],
        )

    def friendly_error(self, message: str) -> str:
        return f"友好:{message}"


def test_skip_policy_logs_authority_skips_when_done(monkeypatch) -> None:
    adapter = _FakeAdapter()
    bind = SimpleNamespace(member_id=1, id=10)
    done = [_result("already")]

    monkeypatch.setattr(
        "app.services.checkin_orchestrator.today_done_from_logs",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.load_day_checkin_results",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.day_results_payload",
        lambda results: {
            "summary": "今日已签到",
            "results": [r.to_api_dict() for r in results],
            "ok": True,
        },
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.today",
        lambda: date(2026, 8, 6),
    )

    out = run_checkin_for_bind(adapter, MagicMock(), bind, force=False)
    assert out["skipped"] is True
    assert out["reason"] == "today_done"
    assert adapter.runs == 0


def test_skip_policy_always_run_ignores_logs(monkeypatch) -> None:
    adapter = _FakeAdapter()
    adapter.skip_policy = SkipPolicy.ALWAYS_RUN
    bind = SimpleNamespace(
        member_id=1,
        id=10,
        last_checkin_date=None,
        last_checkin_ok=False,
    )

    monkeypatch.setattr(
        "app.services.checkin_orchestrator.today",
        lambda: date(2026, 8, 6),
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.now_naive",
        lambda: date(2026, 8, 6),
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.apply_bind_last_checkin",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.upsert_and_reload_day_results",
        lambda *a, **k: [_result("ok")],
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.results_to_api",
        lambda results: [r.to_api_dict() for r in results],
    )

    out = run_checkin_for_bind(adapter, MagicMock(), bind, force=False)
    assert out["skipped"] is False
    assert out["ok"] is True
    assert adapter.runs == 1
    assert adapter.saved
    assert out["exchanges"]
    assert out["exchanges"][0]["upstream_response"] == '{"code":0}'
    # 用户侧 results 不含 upstream
    assert "upstream_response" not in (out["results"][0] or {})


def test_skip_returns_empty_exchanges(monkeypatch) -> None:
    adapter = _FakeAdapter()
    bind = SimpleNamespace(member_id=1, id=10)
    done = [_result("already")]

    monkeypatch.setattr(
        "app.services.checkin_orchestrator.today_done_from_logs",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.load_day_checkin_results",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.day_results_payload",
        lambda results: {
            "summary": "今日已签到",
            "results": [r.to_api_dict() for r in results],
            "ok": True,
        },
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.today",
        lambda: date(2026, 8, 6),
    )

    out = run_checkin_for_bind(adapter, MagicMock(), bind, force=False)
    assert out["exchanges"] == []


def test_query_today_uses_cache(monkeypatch) -> None:
    adapter = _FakeAdapter()
    bind = SimpleNamespace(member_id=1, id=10)
    cached = [_result("already")]

    monkeypatch.setattr(
        "app.services.checkin_orchestrator.today",
        lambda: date(2026, 8, 6),
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.load_day_checkin_results",
        lambda *a, **k: cached,
    )
    monkeypatch.setattr(
        "app.services.checkin_orchestrator.day_results_payload",
        lambda results: {"ok": True, "results": results, "summary": "s"},
    )

    out = query_today_for_bind(adapter, MagicMock(), bind, force=False)
    assert out["ok"] is True
    assert adapter.queries == 0


def test_registry_has_checkin_platforms() -> None:
    from app.services.checkin_registry import get_checkin_adapters
    from app.services.checkin_role_prefs import (
        PLATFORM_EXILIUM,
        PLATFORM_KUJIEQU,
        PLATFORM_MIHOYO,
        PLATFORM_SKLAND,
        PLATFORM_TAYGEDO,
    )

    adapters = get_checkin_adapters()
    assert set(adapters) == {
        PLATFORM_SKLAND,
        PLATFORM_TAYGEDO,
        PLATFORM_EXILIUM,
        PLATFORM_KUJIEQU,
        PLATFORM_MIHOYO,
    }
