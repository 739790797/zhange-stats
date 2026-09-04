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
    monkeypatch.setattr(
        rh, "get_settings", lambda: MagicMock(REDIS_URL="", is_production=False)
    )
    item = rh._probe_redis()
    assert item.id == "redis"
    assert item.status == "skipped"
    assert "未配置" in item.detail


def test_probe_redis_degraded_in_production_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rh, "get_settings", lambda: MagicMock(REDIS_URL="", is_production=True)
    )
    item = rh._probe_redis()
    assert item.status == "degraded"


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
        "_probe_app_env",
        lambda: rh.ServiceHealthItem("app_env", "运行环境", "skipped", detail="dev"),
    )
    monkeypatch.setattr(
        rh,
        "_probe_xff",
        lambda: rh.ServiceHealthItem("xff", "X-Forwarded-For", "skipped", detail="off"),
    )
    monkeypatch.setattr(
        rh,
        "_probe_smtp",
        lambda _db: rh.ServiceHealthItem("smtp", "SMTP", "skipped", detail="n/a"),
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
        "app_env",
        "xff",
        "smtp",
    ]
    sched = next(s for s in report.services if s.id == "scheduler")
    assert sched.status == "ok"
