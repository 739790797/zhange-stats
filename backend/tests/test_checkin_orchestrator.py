"""签到编排 / Adapter 单测（假 Adapter，不打上游）。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.checkin.adapter import (
    CheckinAdapterBase,
    CheckinRunOutcome,
    SkipPolicy,
)
from app.services.checkin.common import CheckinResult
from app.services.checkin.orchestrator import (
    _job_lock_for,
    checkin_job_wrapper,
    query_today_for_bind,
    run_checkin_for_bind,
    run_checkin_job,
)
from app.services.checkin.role_prefs import RoleKey


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
        "app.services.checkin.orchestrator.today_done_from_logs",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.load_day_checkin_results",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.day_results_payload",
        lambda results: {
            "summary": "今日已签到",
            "results": [r.to_api_dict() for r in results],
            "ok": True,
        },
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.today",
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
    )

    monkeypatch.setattr(
        "app.services.checkin.orchestrator.today",
        lambda: date(2026, 8, 6),
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.now_naive",
        lambda: date(2026, 8, 6),
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.upsert_and_reload_day_results",
        lambda *a, **k: [_result("ok")],
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.results_to_api",
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
        "app.services.checkin.orchestrator.today_done_from_logs",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.load_day_checkin_results",
        lambda *a, **k: done,
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.day_results_payload",
        lambda results: {
            "summary": "今日已签到",
            "results": [r.to_api_dict() for r in results],
            "ok": True,
        },
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.today",
        lambda: date(2026, 8, 6),
    )

    out = run_checkin_for_bind(adapter, MagicMock(), bind, force=False)
    assert out["exchanges"] == []


def test_query_today_uses_cache(monkeypatch) -> None:
    adapter = _FakeAdapter()
    bind = SimpleNamespace(member_id=1, id=10)
    cached = [_result("already")]

    monkeypatch.setattr(
        "app.services.checkin.orchestrator.today",
        lambda: date(2026, 8, 6),
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.load_day_checkin_results",
        lambda *a, **k: cached,
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.day_results_payload",
        lambda results: {"ok": True, "results": results, "summary": "s"},
    )

    out = query_today_for_bind(adapter, MagicMock(), bind, force=False)
    assert out["ok"] is True
    assert adapter.queries == 0


def test_upstream_error_without_renewal_hook_is_not_retried() -> None:
    adapter = _FakeAdapter()
    loads: list[object] = []

    def load_session(_db, bind):
        loads.append(bind)
        return {"token": "t"}

    def reject(_session):
        raise _FakeApiError("401 未登录", code=401)

    adapter.load_session = load_session  # type: ignore[method-assign]
    adapter.query_today_all = reject  # type: ignore[method-assign]
    bind = SimpleNamespace(member_id=1, id=10)

    with pytest.raises(_FakeApiError, match="友好:401 未登录"):
        query_today_for_bind(adapter, MagicMock(), bind, force=True)
    assert loads == [bind]


def test_early_response_still_persists_rotated_session() -> None:
    adapter = _FakeAdapter()
    adapter.skip_policy = SkipPolicy.ALWAYS_RUN
    events: list[object] = []
    db = MagicMock()
    db.commit.side_effect = lambda: events.append("commit")

    def no_targets(session, *, force, role_keys):
        return CheckinRunOutcome(
            session={"token": "rotated"},
            early_response={"skipped": False, "ok": False, "summary": "未找到可签到目标", "results": []},
        )

    adapter.run_checkins = no_targets  # type: ignore[method-assign]
    adapter.save_session = lambda _db, _bind, session: events.append(session)  # type: ignore[method-assign]

    out = run_checkin_for_bind(adapter, db, SimpleNamespace(member_id=1, id=10), force=False)

    assert out["no_targets"] is True
    assert events[-2:] == [{"token": "rotated"}, "commit"]


def test_checkin_job_releases_lock_when_pool_times_out(monkeypatch) -> None:
    """开库失败不能占住平台锁，否则下一分钟会静默跳过。"""
    adapter = _FakeAdapter()
    adapter.platform = "lock-release"
    opens = {"n": 0}

    def open_session():
        opens["n"] += 1
        raise TimeoutError("QueuePool limit reached")

    monkeypatch.setattr("app.core.database.SessionLocal", open_session)

    checkin_job_wrapper(adapter)
    checkin_job_wrapper(adapter)

    assert opens["n"] == 2
    lock = _job_lock_for(adapter.platform)
    assert lock.acquire(blocking=False)
    lock.release()


class _RecordingJob:
    id = 1

    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class _RecordingDb:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, job: object) -> None:
        self.added.append(job)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_checkin_job_marks_error_when_any_member_fails(monkeypatch) -> None:
    adapter = _FakeAdapter()
    adapter.platform = "partial-fail"
    db = _RecordingDb()

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("app.services.checkin.orchestrator.JobRun", _RecordingJob)
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.collect_checkin_job_targets",
        lambda *a, **k: {1: None, 2: None, 3: None},
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.run_checkin_job",
        lambda *a, **k: {"ok": 2, "failed": 1, "skipped": 0, "total": 3},
    )

    checkin_job_wrapper(adapter)
    (job,) = db.added
    assert job.status == "error"
    assert "失败 1" in str(job.message)


def test_due_checkin_job_with_nobody_due_writes_no_run(monkeypatch, caplog) -> None:
    """每分钟巡检空跑：不建 JobRun、不打 INFO。"""
    adapter = _FakeAdapter()
    adapter.platform = "idle"
    db = _RecordingDb()
    ran: list[object] = []

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("app.services.checkin.orchestrator.JobRun", _RecordingJob)
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.collect_checkin_job_targets",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.run_checkin_job",
        lambda *a, **k: ran.append(k) or {},
    )

    with caplog.at_level("INFO", logger="app.services.checkin.orchestrator"):
        checkin_job_wrapper(adapter, due_only=True)

    assert db.added == []
    assert ran == []
    assert not [r for r in caplog.records if r.levelno >= 20]
    lock = _job_lock_for(adapter.platform)
    assert lock.acquire(blocking=False)
    lock.release()


def test_manual_checkin_job_with_no_targets_still_records_run(monkeypatch) -> None:
    adapter = _FakeAdapter()
    adapter.platform = "manual-empty"
    db = _RecordingDb()
    seen: dict[str, object] = {}

    def fake_run(*_a, **kwargs):
        seen.update(kwargs)
        return {"ok": 0, "failed": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("app.services.checkin.orchestrator.JobRun", _RecordingJob)
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.collect_checkin_job_targets",
        lambda *a, **k: {},
    )
    monkeypatch.setattr("app.services.checkin.orchestrator.run_checkin_job", fake_run)

    checkin_job_wrapper(adapter, due_only=False, member_id=7)

    (job,) = db.added
    assert job.status == "ok"
    assert seen["targets"] == {}
    assert seen["member_id"] == 7


def test_checkin_job_crash_rolls_back_before_writing_error(monkeypatch) -> None:
    adapter = _FakeAdapter()
    adapter.platform = "crash"
    db = _RecordingDb()
    failed: list[tuple[int, str]] = []

    def boom(*_a, **_k):
        raise RuntimeError("db went away")

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
    monkeypatch.setattr("app.services.checkin.orchestrator.JobRun", _RecordingJob)
    monkeypatch.setattr(
        "app.services.checkin.orchestrator.collect_checkin_job_targets",
        lambda *a, **k: {1: None},
    )
    monkeypatch.setattr("app.services.checkin.orchestrator.run_checkin_job", boom)
    monkeypatch.setattr(
        "app.services.job_runs_prune.fail_job_run",
        lambda _db, run_id, message, **_k: failed.append((run_id, message)),
    )

    checkin_job_wrapper(adapter, due_only=True)

    assert failed == [(1, "db went away")]


def _job_db_with_binds(member_ids: list[int]):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base
    from app.models.member import Member
    from app.models.skland import SklandBind

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    for mid in member_ids:
        db.add(Member(id=mid, nickname=f"m{mid}"))
        db.add(SklandBind(member_id=mid, token_enc="x", auto_checkin=True))
    db.commit()
    return db


class _BindAdapter(_FakeAdapter):
    platform = "attempts-fake"

    def __init__(self) -> None:
        super().__init__()
        from app.models.skland import SklandBind

        self.bind_model = SklandBind


def test_due_job_records_retry_ledger_per_outcome(monkeypatch) -> None:
    from datetime import datetime

    from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
    from app.core.timeutil import BEIJING
    from app.services.checkin.attempts import (
        TERMINAL_AUTH,
        TERMINAL_DONE,
        load_attempts,
    )

    reset_ephemeral_kv_for_tests()
    adapter = _BindAdapter()
    db = _job_db_with_binds([1, 2, 3, 4])
    now = datetime(2026, 9, 24, 0, 6, 30, tzinfo=BEIJING)
    role = ("g", "1")

    def fake_run(_adapter, _db, bind, *, force, role_keys):
        assert force is False
        if bind.member_id == 1:
            raise _FakeApiError("凭证可能已失效，请重新绑定森空岛（401）")
        if bind.member_id == 2:
            raise _FakeApiError("网络异常，请稍后重试（timeout）")
        if bind.member_id == 3:
            return {"skipped": True, "ok": True, "results": []}
        raise ValueError("bug")

    monkeypatch.setattr("app.services.checkin.orchestrator.run_checkin_for_bind", fake_run)

    stats = run_checkin_job(
        adapter,
        db,
        due_only=True,
        targets={1: {role}, 2: {role}, 3: {role}, 4: None},
        now=now,
    )

    assert stats == {"total": 4, "ok": 0, "failed": 3, "skipped": 1}
    auth = load_attempts(adapter.platform, 1, now=now)["g/1"]
    assert (auth.attempts, auth.terminal) == (1, TERMINAL_AUTH)
    network = load_attempts(adapter.platform, 2, now=now)["g/1"]
    assert network.terminal is None
    assert not network.ready(now)
    assert load_attempts(adapter.platform, 3, now=now)["g/1"].terminal == TERMINAL_DONE
    crashed = load_attempts(adapter.platform, 4, now=now)["*"]
    assert crashed.attempts == 1 and crashed.terminal is None
    reset_ephemeral_kv_for_tests()


def test_manual_job_does_not_touch_retry_ledger(monkeypatch) -> None:
    from datetime import datetime

    from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
    from app.core.timeutil import BEIJING
    from app.services.checkin.attempts import load_attempts

    reset_ephemeral_kv_for_tests()
    adapter = _BindAdapter()
    db = _job_db_with_binds([1])
    now = datetime(2026, 9, 24, 9, 0, tzinfo=BEIJING)

    def fake_run(*_a, **_k):
        raise _FakeApiError("网络异常")

    monkeypatch.setattr("app.services.checkin.orchestrator.run_checkin_for_bind", fake_run)

    stats = run_checkin_job(adapter, db, due_only=False, targets={1: None}, now=now)

    assert stats["failed"] == 1
    assert load_attempts(adapter.platform, 1, now=now) == {}


def test_repeated_expected_failure_logs_warning_once(monkeypatch, caplog) -> None:
    from datetime import datetime

    from app.core.biz_logging import clear_log_until_change
    from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
    from app.core.timeutil import BEIJING

    reset_ephemeral_kv_for_tests()
    clear_log_until_change()
    adapter = _BindAdapter()
    db = _job_db_with_binds([1])
    now = datetime(2026, 9, 24, 9, 0, tzinfo=BEIJING)

    def fake_run(*_a, **_k):
        raise _FakeApiError("网络异常")

    monkeypatch.setattr("app.services.checkin.orchestrator.run_checkin_for_bind", fake_run)

    with caplog.at_level("DEBUG", logger="app.services.checkin.orchestrator"):
        for _ in range(3):
            run_checkin_job(adapter, db, due_only=False, targets={1: None}, now=now)

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert not [r for r in caplog.records if r.levelname == "ERROR"]
    clear_log_until_change()


def test_no_matching_roles_marks_no_targets() -> None:
    adapter = _FakeAdapter()

    def early(session, *, force, role_keys):
        return CheckinRunOutcome(
            session=session,
            early_response={"skipped": False, "ok": False, "summary": "无", "results": []},
        )

    adapter.run_checkins = early  # type: ignore[method-assign]
    adapter.skip_policy = SkipPolicy.ALWAYS_RUN
    out = run_checkin_for_bind(
        adapter, MagicMock(), SimpleNamespace(member_id=1, id=10), role_keys={("g", "x")}
    )
    assert out["no_targets"] is True

    def filtered(session, *, force, role_keys):
        return CheckinRunOutcome(
            session=session,
            early_response={"skipped": True, "ok": True, "summary": "无需", "results": []},
        )

    adapter.run_checkins = filtered  # type: ignore[method-assign]
    out = run_checkin_for_bind(
        adapter, MagicMock(), SimpleNamespace(member_id=1, id=10), role_keys={("g", "x")}
    )
    assert out["no_targets"] is False


def test_registry_has_checkin_platforms() -> None:
    from app.services.checkin.registry import get_checkin_adapters
    from app.services.checkin.role_prefs import (
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
