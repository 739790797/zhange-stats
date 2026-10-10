"""调度注册：每日 cron 补跑窗口；签到入口从注册表派生。"""

from __future__ import annotations

from app.services import scheduler_runtime as sr
from app.services.checkin.orchestrator import checkin_job_wrapper
from app.services.checkin.registry import get_checkin_adapters


class _FakeScheduler:
    running = True

    def __init__(self) -> None:
        self.jobs: dict[str, tuple[str, dict]] = {}

    def add_job(self, func, trigger, **kwargs) -> None:
        self.jobs[kwargs["id"]] = (trigger, kwargs)

    def remove_job(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)


def _register(monkeypatch) -> _FakeScheduler:
    monkeypatch.setattr(sr, "load_scheduler_config", lambda _db: {})
    monkeypatch.setattr(sr, "get_steam_api_key", lambda _db: "")
    monkeypatch.setattr(sr, "_job_feature_allowed", lambda _db, _job_id: True)
    scheduler = _FakeScheduler()
    assert sr.register_scheduler_jobs(scheduler, None) is True
    return scheduler


def test_daily_cron_jobs_catch_up_once_after_short_misfire(monkeypatch) -> None:
    scheduler = _register(monkeypatch)

    for job_id in sr.SYSTEM_CRON_HANDLERS:
        trigger, kwargs = scheduler.jobs[job_id]
        assert trigger == "cron"
        assert kwargs["coalesce"] is True
        assert kwargs["misfire_grace_time"] == sr.SYSTEM_CRON_MISFIRE_GRACE_SECONDS


def test_checkin_jobs_come_from_adapter_registry(monkeypatch) -> None:
    adapters = {a.job_key: a for a in get_checkin_adapters().values()}
    assert set(sr.CHECKIN_JOB_IDS) == set(adapters)

    for job_id, adapter in adapters.items():
        due = sr.CHECKIN_DUE_HANDLERS[job_id]
        assert due.func is checkin_job_wrapper
        assert due.args == (adapter,)
        assert due.keywords == {"due_only": True}
        manual = sr.CHECKIN_MANUAL_HANDLERS[job_id]
        assert manual.func is checkin_job_wrapper
        assert manual.args == (adapter,)

    scheduler = _register(monkeypatch)
    for job_id in adapters:
        trigger, kwargs = scheduler.jobs[job_id]
        assert trigger == "interval"
        assert kwargs["minutes"] == 1
