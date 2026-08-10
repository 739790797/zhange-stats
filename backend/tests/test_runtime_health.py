"""Unit tests for multi-service runtime health aggregation."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.core.timeutil import now_naive
from app.services import runtime_health as rh


def test_overall_prefers_error_then_degraded() -> None:
    assert (
        rh._overall(
            [
                rh.ServiceHealthItem("a", "A", "ok"),
                rh.ServiceHealthItem("b", "B", "skipped"),
            ]
        )
        == "ok"
    )
    assert (
        rh._overall(
            [
                rh.ServiceHealthItem("a", "A", "ok"),
                rh.ServiceHealthItem("b", "B", "offline"),
            ]
        )
        == "degraded"
    )
    assert (
        rh._overall(
            [
                rh.ServiceHealthItem("a", "A", "degraded"),
                rh.ServiceHealthItem("b", "B", "error"),
            ]
        )
        == "error"
    )


def test_probe_redis_skipped_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rh, "get_settings", lambda: MagicMock(REDIS_URL=""))
    item = rh._probe_redis()
    assert item.id == "redis"
    assert item.status == "skipped"
    assert "未配置" in item.detail


def test_probe_maa_worker_skipped_without_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rh, "get_maa_host_stats", lambda _db: {})
    monkeypatch.setattr(
        rh,
        "get_settings",
        lambda: MagicMock(MAA_ENABLED=False),
    )
    item = rh._probe_maa_worker(MagicMock())
    assert item.status == "skipped"


def test_probe_maa_worker_ok_fresh_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    reported = now_naive().isoformat(timespec="seconds")
    monkeypatch.setattr(
        rh,
        "get_maa_host_stats",
        lambda _db: {"reported_at": reported, "cpu_percent": "12.5"},
    )
    monkeypatch.setattr(rh, "maa_stale_threshold_sec", lambda: 30)
    item = rh._probe_maa_worker(MagicMock())
    assert item.status == "ok"
    assert "心跳" in item.detail


def test_probe_maa_worker_offline_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = (now_naive() - timedelta(seconds=120)).isoformat(timespec="seconds")
    monkeypatch.setattr(
        rh,
        "get_maa_host_stats",
        lambda _db: {"reported_at": stale},
    )
    monkeypatch.setattr(rh, "maa_stale_threshold_sec", lambda: 30)
    item = rh._probe_maa_worker(MagicMock())
    assert item.status == "offline"
    assert "过期" in item.detail


def test_probe_maa_slots_degraded_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rh,
        "resource_summary",
        lambda _db: {
            "max_slots": 4,
            "active_slots": 2,
            "online": 1,
            "offline": 0,
            "error": 1,
            "busy": 0,
        },
    )
    monkeypatch.setattr(rh, "get_settings", lambda: MagicMock(MAA_ENABLED=True))
    item = rh._probe_maa_slots(MagicMock())
    assert item.status == "degraded"
    assert "error 1" in item.detail


def test_collect_runtime_health_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rh,
        "_probe_mysql",
        lambda: rh.ServiceHealthItem("mysql", "MySQL", "ok", latency_ms=1.0, detail="ok"),
    )
    monkeypatch.setattr(
        rh,
        "_probe_redis",
        lambda: rh.ServiceHealthItem("redis", "Redis", "skipped", detail="n/a"),
    )
    monkeypatch.setattr(
        rh,
        "_probe_maa_worker",
        lambda _db: rh.ServiceHealthItem("maa_worker", "MAA Worker", "skipped", detail="n/a"),
    )
    monkeypatch.setattr(
        rh,
        "_probe_maa_slots",
        lambda _db: rh.ServiceHealthItem("maa_slots", "MAA 槽位", "skipped", detail="n/a"),
    )
    report = rh.collect_runtime_health(MagicMock(), scheduler_running=True)
    assert report.overall == "ok"
    assert report.checked_at
    ids = [s.id for s in report.services]
    assert ids == [
        "app",
        "mysql",
        "redis",
        "scheduler",
        "maa_worker",
        "maa_slots",
    ]
    sched = next(s for s in report.services if s.id == "scheduler")
    assert sched.status == "ok"
