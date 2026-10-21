from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.job_run import JobRun
from app.services import job_run_progress
from app.services.job_run_progress import (
    SYNC_JOB_CATEGORIES,
    create_or_reuse_job_run,
    create_queued_job_run,
    job_run_context,
    versioned_job_stats,
    write_job_run,
)


def test_sync_job_categories_are_declared() -> None:
    assert SYNC_JOB_CATEGORIES["endfield_repo_sync"] == "repository"
    assert SYNC_JOB_CATEGORIES["tarkov_full_sync"] == "data_pipeline"
    assert SYNC_JOB_CATEGORIES["arknights_box_sync"] == "batch_sync"
    assert SYNC_JOB_CATEGORIES["texteller_model_sync"] == "asset_sync"


def test_versioned_stats_only_publish_measured_percentages() -> None:
    unknown = versioned_job_stats(
        "tarkov_full_sync", status="running", stats={"phase": "download", "percent": 45}
    )
    assert unknown is not None
    assert unknown["schema_version"] == 1
    assert unknown["category"] == "data_pipeline"
    assert unknown["percent"] == 45  # legacy readers retain the old field
    assert unknown["progress"] == {}

    measured = versioned_job_stats(
        "texteller_model_sync",
        status="running",
        stats={"phase": "download", "files_done": 3, "files_total": 8},
    )
    assert measured is not None
    assert measured["progress"] == {
        "current": 3.0,
        "total": 8.0,
        "unit": "个文件",
        "percent": 38,
    }


def test_manual_run_reuses_queued_row_and_records_warning(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    JobRun.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(job_run_progress, "SessionLocal", factory)

    db = factory()
    queued = create_queued_job_run(db, "arknights_box_sync", "batch_sync")
    run_id = queued.id

    with job_run_context("arknights_box_sync", run_id):
        reused = create_or_reuse_job_run(
            db,
            "arknights_box_sync",
            message="正在同步干员练度",
            stats={"phase": "start"},
        )
        db.commit()
        assert reused.id == run_id
        assert db.query(JobRun).filter_by(job_key="arknights_box_sync").count() == 1

        write_job_run(
            run_id,
            "arknights_box_sync",
            status="warning",
            message="成功 4，失败 1",
            stats={
                "phase": "done",
                "ok": 4,
                "failed": 1,
                "result": {
                    "summary": "干员练度同步完成：成功 4，失败 1",
                    "counts": {"ok": 4, "failed": 1},
                },
            },
            finished=True,
        )

    db.expire_all()
    row = db.get(JobRun, run_id)
    assert row is not None
    assert row.status == "warning"
    assert row.finished_at is not None
    assert row.stats["category"] == "batch_sync"
    assert row.stats["result"]["counts"] == {"ok": 4, "failed": 1}
    assert row.stats["steps"][0]["status"] == "warning"
    db.close()
    engine.dispose()
