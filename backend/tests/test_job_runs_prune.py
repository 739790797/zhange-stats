"""job_runs 收尾与清理：失败回写先 rollback、僵尸 running 不挡手动触发、过期验证码 / 换票清理。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.api.jobs.helpers import _job_has_running_run, _last_runs_by_key
from app.core.database import Base
from app.core.timeutil import now_naive
from app.models.job_run import JobRun
from app.models.oauth_ticket import OAuthExchangeTicket
from app.models.register_challenge import RegisterChallenge
from app.services.job_runs_prune import (
    CHALLENGE_PRUNE_GRACE,
    STALE_RUNNING_AFTER,
    fail_job_run,
    prune_expired_auth_rows,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            JobRun.__table__,
            RegisterChallenge.__table__,
            OAuthExchangeTicket.__table__,
        ],
    )
    return sessionmaker(bind=engine)()


def test_fail_job_run_recovers_from_failed_transaction() -> None:
    db = _session()
    run = JobRun(job_key="steam_presence", status="running", started_at=now_naive())
    db.add(run)
    db.commit()
    run_id = run.id

    db.add(JobRun(job_key=None, status="running", started_at=now_naive()))
    with pytest.raises(IntegrityError):
        db.flush()

    fail_job_run(db, run_id, "boom", stats={"failed": 1})

    db.expire_all()
    row = db.get(JobRun, run_id)
    assert row is not None
    assert row.status == "error"
    assert row.message == "boom"
    assert row.stats == {"failed": 1}
    assert row.finished_at is not None


def test_fail_job_run_missing_row_is_noop() -> None:
    db = _session()
    fail_job_run(db, 404, "gone")
    assert db.query(JobRun).count() == 0


def test_stale_running_row_does_not_block_trigger() -> None:
    db = _session()
    db.add(
        JobRun(
            job_key="tarkov_full_sync",
            status="running",
            started_at=now_naive() - STALE_RUNNING_AFTER - timedelta(minutes=1),
        )
    )
    db.commit()
    assert _job_has_running_run(db, "tarkov_full_sync") is False

    db.add(
        JobRun(
            job_key="tarkov_full_sync",
            status="running",
            started_at=now_naive() - timedelta(hours=1),
        )
    )
    db.commit()
    assert _job_has_running_run(db, "tarkov_full_sync") is True


def test_last_runs_by_key_not_crowded_out_by_frequent_jobs() -> None:
    db = _session()
    base = now_naive()
    db.add(
        JobRun(
            job_key="arknights_box_sync",
            status="ok",
            started_at=base - timedelta(days=1),
        )
    )
    for i in range(30):
        db.add(
            JobRun(
                job_key="skland_checkin",
                status="ok",
                started_at=base - timedelta(minutes=i),
            )
        )
    db.commit()

    lasts = _last_runs_by_key(db, ["skland_checkin", "arknights_box_sync", "never_ran"])
    assert set(lasts) == {"skland_checkin", "arknights_box_sync"}
    assert lasts["skland_checkin"].started_at == base
    assert lasts["arknights_box_sync"].status == "ok"


def test_prune_expired_auth_rows() -> None:
    db = _session()
    now = now_naive()
    db.add_all(
        [
            RegisterChallenge(
                email="old@example.com",
                purpose="register",
                code="111111",
                expires_at=now - CHALLENGE_PRUNE_GRACE - timedelta(minutes=1),
            ),
            # 刚过期：留着，提交旧码仍提示「已过期」
            RegisterChallenge(
                email="recent@example.com",
                purpose="register",
                code="222222",
                expires_at=now - timedelta(minutes=5),
            ),
            RegisterChallenge(
                email="live@example.com",
                purpose="register",
                code="333333",
                expires_at=now + timedelta(minutes=5),
            ),
            OAuthExchangeTicket(
                code="expired", access_token="enc:v1:x", expires_at=now - timedelta(seconds=1)
            ),
            OAuthExchangeTicket(
                code="live", access_token="enc:v1:y", expires_at=now + timedelta(minutes=1)
            ),
        ]
    )
    db.commit()

    assert prune_expired_auth_rows(db) == {
        "register_challenges": 1,
        "oauth_exchange_tickets": 1,
    }
    db.commit()
    assert {r.email for r in db.query(RegisterChallenge).all()} == {
        "recent@example.com",
        "live@example.com",
    }
    assert [t.code for t in db.query(OAuthExchangeTicket).all()] == ["live"]
