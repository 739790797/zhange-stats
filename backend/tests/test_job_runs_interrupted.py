"""启动回收：上个进程遗留的 running 任务记录收尾为 error，不再挡手动触发。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.job_run import JobRun
from app.services.job_runs_prune import INTERRUPTED_MESSAGE, mark_interrupted_job_runs


def _session():
    engine = create_engine("sqlite:///:memory:")
    JobRun.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


def test_marks_only_running_rows() -> None:
    db = _session()
    db.add_all(
        [
            JobRun(job_key="steam_presence", status="running"),
            JobRun(job_key="tarkov_sync", status="running"),
            JobRun(job_key="steam_presence", status="ok", message="done"),
        ]
    )
    db.commit()

    assert mark_interrupted_job_runs(db) == 2

    rows = {r.job_key + ":" + r.status: r for r in db.query(JobRun).all()}
    assert "steam_presence:running" not in rows
    interrupted = [r for r in db.query(JobRun).filter(JobRun.message == INTERRUPTED_MESSAGE)]
    assert len(interrupted) == 2
    assert all(r.status == "error" and r.finished_at is not None for r in interrupted)
    assert db.query(JobRun).filter(JobRun.status == "ok").count() == 1


def test_no_running_rows_is_noop() -> None:
    db = _session()
    db.add(JobRun(job_key="steam_presence", status="ok"))
    db.commit()
    assert mark_interrupted_job_runs(db) == 0
