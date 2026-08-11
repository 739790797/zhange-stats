"""Unit tests for multi-service runtime health aggregation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
    report = rh.collect_runtime_health(MagicMock(), scheduler_running=True)
    assert report.overall == "ok"
    assert report.checked_at
    ids = [s.id for s in report.services]
    assert ids == [
        "app",
        "mysql",
        "redis",
        "scheduler",
    ]
    sched = next(s for s in report.services if s.id == "scheduler")
    assert sched.status == "ok"
