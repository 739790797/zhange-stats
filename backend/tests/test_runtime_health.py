"""Unit tests for multi-service runtime health aggregation."""

from __future__ import annotations

from pathlib import Path
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


def test_redact_conn_error_strips_url_credentials() -> None:
    err = RuntimeError(
        "Can't connect using mysql+pymysql://root:s3cret@127.0.0.1:3306/zhange"
    )
    text = rh.redact_conn_error(err)
    assert "s3cret" not in text
    assert "mysql+pymysql://***@" in text


def test_probe_database_rejects_bad_engine() -> None:
    result = rh.probe_database_settings(engine="postgres")
    assert result.ok is False
    assert "sqlite" in result.message


def test_probe_database_rejects_non_mysql_url() -> None:
    result = rh.probe_database_settings(engine="mysql", url="postgres://x")
    assert result.ok is False
    assert "MySQL" in result.message


def test_probe_sqlite_ok(tmp_path: Path) -> None:
    dest = tmp_path / "db" / "probe.sqlite"
    dest.parent.mkdir()
    result = rh.probe_database_settings(engine="sqlite", path=str(dest))
    assert result.ok is True
    assert result.latency_ms is not None
    assert dest.is_file()


def test_probe_sqlite_missing_parent(tmp_path: Path) -> None:
    dest = tmp_path / "missing" / "probe.sqlite"
    result = rh.probe_database_settings(engine="sqlite", path=str(dest))
    assert result.ok is False
    assert "目录不存在" in result.message


def test_probe_redis_requires_host() -> None:
    result = rh.probe_redis_url("")
    assert result.ok is False
    assert "主机" in result.message


def test_probe_redis_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import redis

    client = MagicMock()
    client.ping.return_value = True
    monkeypatch.setattr(redis.Redis, "from_url", lambda *a, **k: client)
    result = rh.probe_redis_url("redis://127.0.0.1:6379/0")
    assert result.ok is True
    client.ping.assert_called_once()
    client.close.assert_called_once()


def test_probe_redis_redacts_password(monkeypatch: pytest.MonkeyPatch) -> None:
    import redis

    def boom(*_a, **_k):
        raise ConnectionError("Error connecting to redis://:hunter2@127.0.0.1:6379/0")

    monkeypatch.setattr(redis.Redis, "from_url", boom)
    result = rh.probe_redis_url("redis://:hunter2@127.0.0.1:6379/0")
    assert result.ok is False
    assert "hunter2" not in result.message


def test_collect_runtime_health_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rh,
        "_probe_database",
        lambda: rh.ServiceHealthItem(
            "database", "数据库", "ok", latency_ms=1.0, detail="ok"
        ),
    )
    monkeypatch.setattr(
        rh,
        "_probe_redis",
        lambda: rh.ServiceHealthItem("redis", "Redis", "skipped", detail="n/a"),
    )
    report = rh.collect_runtime_health()
    assert report.overall == "ok"
    assert report.checked_at
    ids = [s.id for s in report.services]
    assert ids == ["database", "redis"]
    assert "smtp" not in ids
    assert "scheduler" not in ids
    assert "app_env" not in ids
    assert "xff" not in ids
