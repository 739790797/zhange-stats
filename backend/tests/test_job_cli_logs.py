from __future__ import annotations

import io
import logging
import subprocess
import threading
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.cli import __main__ as cli
from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.job_run import JobRun
from app.models.job_run_log import JobRunLog
from app.services import job_run_logs, job_runner
from app.services.job_execution_lock import (
    JobExecutionBusy,
    JobExecutionLockUnavailable,
    job_execution_lock,
)
from app.services.job_run_progress import SYNC_JOB_CATEGORIES
from app.services.scheduler_runtime import SYSTEM_CRON_HANDLERS


def _job_db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'job-runs.sqlite'}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine, tables=[JobRun.__table__, JobRunLog.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(job_run_logs, "SessionLocal", factory)
    monkeypatch.setattr(job_runner, "SessionLocal", factory)
    from app.services import job_run_progress

    monkeypatch.setattr(job_run_progress, "SessionLocal", factory)
    return engine, factory


def test_cli_dispatches_each_registered_sync_job(monkeypatch) -> None:
    resolved: list[str] = []
    executed: list[tuple[str, int | None, bool]] = []
    monkeypatch.setattr(cli, "_configure_logging", lambda **_kwargs: None)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        "app.services.scheduler_runtime.resolve_sync_job_handler",
        lambda job_id, _db: (resolved.append(job_id) or (lambda: None)),
    )
    monkeypatch.setattr(
        "app.services.job_runner.execute_sync_job",
        lambda job_id, _handler, *, run_id, capture_logs: (
            executed.append((job_id, run_id, capture_logs)) or (run_id or 1, "ok")
        ),
    )

    assert len(SYNC_JOB_CATEGORIES) == 12
    assert set(SYNC_JOB_CATEGORIES) <= set(SYSTEM_CRON_HANDLERS)
    for job_id in SYNC_JOB_CATEGORIES:
        assert cli.main(["run-job", job_id]) == 0

    assert resolved == list(SYNC_JOB_CATEGORIES)
    assert executed == [(job_id, None, True) for job_id in SYNC_JOB_CATEGORIES]


def test_cli_rejects_unknown_job_and_web_child_reuses_run_id(monkeypatch) -> None:
    resolved: list[str] = []
    executed: list[tuple[str, int | None, bool]] = []
    monkeypatch.setattr(cli, "_configure_logging", lambda **_kwargs: None)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        "app.services.scheduler_runtime.resolve_sync_job_handler",
        lambda job_id, _db: (resolved.append(job_id) or (lambda: None)),
    )
    monkeypatch.setattr(
        "app.services.job_runner.execute_sync_job",
        lambda job_id, _handler, *, run_id, capture_logs: (
            executed.append((job_id, run_id, capture_logs)) or (run_id or 1, "ok")
        ),
    )

    assert cli.main(["run-job", "not-a-sync-job"]) == 2
    assert cli.main(
        ["run-job", "endfield_repo_sync", "--run-id", "73", "--json-events"]
    ) == 0
    assert resolved == ["endfield_repo_sync"]
    assert executed == [("endfield_repo_sync", 73, False)]


def test_sync_runner_reuses_queued_run_and_records_failure(monkeypatch, tmp_path) -> None:
    engine, factory = _job_db(monkeypatch, tmp_path)

    @contextmanager
    def _lock(_job_id: str):
        yield

    monkeypatch.setattr(job_runner, "job_execution_lock", _lock)

    def _make_task_run() -> None:
        from app.services.job_run_progress import create_or_reuse_job_run

        logging.getLogger("test.sync").info("progress token=secret-value")
        db = factory()
        try:
            create_or_reuse_job_run(
                db, "endfield_repo_sync", message="仓库同步完成", stats={"phase": "done"}
            )
            db.commit()
        finally:
            db.close()

    test_logger = logging.getLogger("test.sync")
    test_logger.setLevel(logging.INFO)
    run_id, status = job_runner.execute_sync_job(
        "endfield_repo_sync", _make_task_run, capture_logs=True
    )
    db = factory()
    row = db.get(JobRun, run_id)
    assert status == "ok"
    assert row is not None and row.status == "ok"
    assert db.query(JobRun).filter_by(job_key="endfield_repo_sync").count() == 1
    stored_logs = db.query(JobRunLog).filter_by(run_id=run_id).all()
    assert any("token=[已隐藏]" in stored_log.message for stored_log in stored_logs)
    db.close()

    def _fail() -> None:
        raise RuntimeError("sync failed")

    with pytest.raises(RuntimeError, match="sync failed"):
        job_runner.execute_sync_job("endfield_repo_sync", _fail)
    db = factory()
    failed = db.query(JobRun).filter_by(status="error").one()
    assert failed.message == "sync failed"
    db.close()
    engine.dispose()


def test_job_run_logs_are_sanitized_capped_and_cursor_readable(monkeypatch, tmp_path) -> None:
    engine, factory = _job_db(monkeypatch, tmp_path)
    monkeypatch.setattr(job_run_logs, "MAX_JOB_RUN_LOGS", 3)
    db = factory()
    run = JobRun(job_key="endfield_repo_sync", status="ok")
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id
    db.close()

    added = job_run_logs.append_job_run_logs(
        run_id,
        [
            job_run_logs.JobRunLogEvent("INFO", "sync", "token=abcd"),
            job_run_logs.JobRunLogEvent("INFO", "sync", "Bearer abc.def.ghi"),
            job_run_logs.JobRunLogEvent("INFO", "sync", '{"payload":"' + ("x" * 250) + '"}'),
            job_run_logs.JobRunLogEvent("INFO", "sync", "fourth line"),
        ],
    )
    rows = job_run_logs.list_job_run_logs(run_id, after_id=0, limit=10)
    assert added == 3
    assert len(rows) == 3
    assert "[已隐藏]" in rows[0].message
    assert "[已隐藏]" in rows[1].message
    assert rows[2].is_truncation is True
    assert job_run_logs.append_job_run_logs(
        run_id, [job_run_logs.JobRunLogEvent("ERROR", "sync", "ignored")]
    ) == 0
    assert [row.id for row in job_run_logs.list_job_run_logs(run_id, after_id=rows[0].id)] == [
        rows[1].id,
        rows[2].id,
    ]
    assert job_run_logs.sanitize_job_log_message(
        'upstream response: {"data":"private"}'
    ) == "upstream response: [结构化上游响应已省略]"
    assert len(job_run_logs.sanitize_job_log_message("终" * 2_000).encode("utf-8")) <= 4_096
    engine.dispose()


def test_job_run_pruning_cascades_to_logs(monkeypatch, tmp_path) -> None:
    from app.services import job_runs_prune

    engine, factory = _job_db(monkeypatch, tmp_path)
    db = factory()
    run = JobRun(
        job_key="endfield_repo_sync",
        status="ok",
        started_at=now_naive() - timedelta(days=10),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id
    db.close()
    job_run_logs.append_job_run_logs(
        run_id, [job_run_logs.JobRunLogEvent("INFO", "sync", "old output")]
    )
    monkeypatch.setattr(job_runs_prune, "prune_checkin_logs", lambda *_a, **_k: {})
    monkeypatch.setattr(job_runs_prune, "maintain_perf_archive", lambda *_a, **_k: {})
    monkeypatch.setattr(job_runs_prune, "prune_rum_samples", lambda *_a, **_k: 0)
    monkeypatch.setattr(job_runs_prune, "prune_expired_auth_rows", lambda *_a, **_k: {})

    db = factory()
    try:
        result = job_runs_prune.prune_job_runs(db, retention_days=7)
        assert result["deleted"] == 1
        assert db.query(JobRunLog).filter_by(run_id=run_id).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_file_execution_lock_releases_after_exception(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.job_execution_lock.get_settings",
        lambda: SimpleNamespace(REDIS_URL=""),
    )
    monkeypatch.setattr("app.services.job_execution_lock.runtime_root", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="force release"):
        with job_execution_lock("endfield_repo_sync"):
            with pytest.raises(JobExecutionBusy):
                with job_execution_lock("endfield_repo_sync"):
                    pass
            raise RuntimeError("force release")

    with job_execution_lock("endfield_repo_sync"):
        pass


def test_configured_unavailable_redis_lock_refuses_run(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.job_execution_lock.get_settings",
        lambda: SimpleNamespace(REDIS_URL="redis://configured"),
    )
    monkeypatch.setattr("app.services.job_execution_lock.get_redis", lambda: None)
    with pytest.raises(JobExecutionLockUnavailable):
        with job_execution_lock("endfield_repo_sync"):
            pass


def test_configured_redis_lock_is_acquired_and_released(monkeypatch) -> None:
    calls: list[str] = []

    class FakeLock:
        def acquire(self, *, blocking: bool) -> bool:
            assert blocking is False
            calls.append("acquired")
            return True

        def owned(self) -> bool:
            return True

        def release(self) -> None:
            calls.append("released")

    class FakeRedis:
        def lock(self, name: str, **kwargs) -> FakeLock:
            assert name == "zhange:job-execution:endfield_repo_sync"
            assert kwargs["timeout"] > 0
            return FakeLock()

    monkeypatch.setattr(
        "app.services.job_execution_lock.get_settings",
        lambda: SimpleNamespace(REDIS_URL="redis://configured"),
    )
    monkeypatch.setattr("app.services.job_execution_lock.get_redis", lambda: FakeRedis())

    with job_execution_lock("endfield_repo_sync"):
        pass

    assert calls == ["acquired", "released"]


def test_process_group_arguments_are_cross_platform(monkeypatch) -> None:
    import subprocess

    from app.services.job_process_supervisor import _platform_process_options

    windows_process_group = 0x00000200
    monkeypatch.setattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", windows_process_group, raising=False
    )
    assert _platform_process_options("nt") == {
        "creationflags": windows_process_group,
    }
    assert _platform_process_options("posix") == {"start_new_session": True}


def test_managed_process_uses_argument_list_and_backend_working_directory(monkeypatch) -> None:
    from app.services import job_process_supervisor as supervisor

    options: list[dict[str, object]] = []

    class FakeProcess:
        stdout = io.StringIO("")
        pid = 123

        def poll(self):
            return None

    class FakeThread:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            pass

    def _popen(**kwargs):
        options.append(kwargs)
        return FakeProcess()

    monkeypatch.setattr(supervisor.subprocess, "Popen", _popen)
    monkeypatch.setattr(supervisor.threading, "Thread", FakeThread)
    monkeypatch.setattr(supervisor, "_PROCESSES", {})

    supervisor.launch_sync_job_process("endfield_repo_sync", 73)

    launched = options[0]
    assert launched["args"] == [
        supervisor.sys.executable,
        "-u",
        "-m",
        "app.cli",
        "run-job",
        "endfield_repo_sync",
        "--run-id",
        "73",
        "--json-events",
    ]
    assert launched["cwd"] == supervisor._BACKEND_ROOT
    assert launched["stdin"] == subprocess.DEVNULL
    assert launched["stdout"] == subprocess.PIPE
    assert launched.get("shell", False) is False


def test_child_nonzero_exit_marks_run_failed(monkeypatch) -> None:
    from app.services import job_process_supervisor as supervisor

    writes: list[dict[str, object]] = []
    monkeypatch.setattr(supervisor, "_read_run_state", lambda _run_id: ("running", "latest progress"))
    monkeypatch.setattr(
        supervisor,
        "write_job_run",
        lambda run_id, job_id, **kwargs: writes.append(
            {"run_id": run_id, "job_id": job_id, **kwargs}
        ),
    )
    monkeypatch.setattr(supervisor, "_STOPPING", threading.Event())

    supervisor._finalize_child("endfield_repo_sync", 73, 4)

    assert writes[0]["status"] == "error"
    assert "latest progress" in str(writes[0]["message"])
    assert "代码 4" in str(writes[0]["message"])
    assert writes[0]["finished"] is True


def test_process_monitor_persists_structured_stdout_events(monkeypatch) -> None:
    from app.services import job_process_supervisor as supervisor

    class FakeProcess:
        stdout = io.StringIO(
            '{"ts":"2026-10-20 12:00:00","level":"WARNING",'
            '"logger":"sync.job","message":"partial result"}\n'
        )

        def wait(self) -> int:
            return 0

        def poll(self) -> int:
            return 0

    stored: list[object] = []
    finalized: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        supervisor,
        "append_job_run_logs",
        lambda run_id, events: stored.extend(events) or len(events),
    )
    monkeypatch.setattr(
        supervisor,
        "_finalize_child",
        lambda job_id, run_id, code: finalized.append((job_id, run_id, code)),
    )
    monkeypatch.setattr(supervisor, "_PROCESSES", {})

    supervisor._monitor_process(
        supervisor.ManagedSyncProcess("endfield_repo_sync", 73, FakeProcess())
    )

    assert len(stored) == 1
    assert stored[0].level == "WARNING"
    assert stored[0].message == "partial result"
    assert finalized == [("endfield_repo_sync", 73, 0)]


def test_shutdown_terminates_managed_processes(monkeypatch) -> None:
    from app.services import job_process_supervisor as supervisor

    terminated: list[int] = []

    class FakeMonitor:
        def join(self, *, timeout: float) -> None:
            assert timeout == 5.0

    entry = SimpleNamespace(
        process=SimpleNamespace(pid=91),
        monitor=FakeMonitor(),
    )
    monkeypatch.setattr(supervisor, "_PROCESSES", {73: entry})
    monkeypatch.setattr(supervisor, "_STOPPING", threading.Event())
    monkeypatch.setattr(
        supervisor,
        "_terminate_process",
        lambda process, *, timeout: terminated.append(process.pid),
    )

    supervisor.stop_all_sync_job_processes()

    assert supervisor._STOPPING.is_set()
    assert terminated == [91]
