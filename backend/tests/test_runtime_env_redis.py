"""运行环境 Redis 地址：GET 不回账号口令与查询串；PUT 回传脱敏地址沿用已存凭据，换主机端口不带走口令；清空要显式。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.settings import (
    RuntimeEnvOut,
    RuntimeEnvUpdate,
    RuntimeRedisTestIn,
    get_runtime_env,
    update_runtime_env,
)
from app.api.settings import test_runtime_redis as probe_runtime_redis
from app.core.config import get_settings
from app.core.file_config import read_json, write_json

ADMIN = object()
STORED = "redis://:s3cret@cache.internal:6380/2?ssl_cert_reqs=none"
MASKED = "redis://cache.internal:6380/2"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("APP_ENV", "REDIS_URL", "DATABASE_URL", "CSP_ENFORCE", "RATE_LIMIT_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _store(url: str) -> None:
    write_json("app", {"REDIS_URL": url})
    get_settings.cache_clear()


def _saved() -> str | None:
    return (read_json("app") or {}).get("REDIS_URL")


def _put(**fields):
    return update_runtime_env(RuntimeEnvUpdate(**fields), ADMIN)


def test_get_hides_password_and_query_string() -> None:
    _store(STORED)
    out = get_runtime_env(ADMIN)
    assert (out["redis_url"], out["redis_url_set"], out["redis_password_set"]) == (MASKED, True, True)
    serialized = RuntimeEnvOut(**out).model_dump_json()
    assert "s3cret" not in serialized
    assert "ssl_cert_reqs" not in serialized


@pytest.mark.parametrize(
    "url,masked,password_set",
    [
        ("redis://localhost:6379/0", "redis://localhost:6379/0", False),
        ("redis://worker:pw@cache.internal", "redis://cache.internal:6379", True),
        ("rediss://cache.internal:6390/1?password=qs-secret", "rediss://cache.internal:6390/1", True),
        ("redis://:pw@[fd00::5]:6379/3", "redis://[fd00::5]:6379/3", True),
        ("unix:///run/redis.sock?password=qs-secret", "", True),
        ("redis://cache.internal:notaport/0", "", False),
        ("", "", False),
    ],
)
def test_masked_shapes(url: str, masked: str, password_set: bool) -> None:
    _store(url)
    out = get_runtime_env(ADMIN)
    assert out["redis_url"] == masked
    assert out["redis_url_set"] is bool(url)
    assert out["redis_password_set"] is password_set


def test_saving_the_masked_value_keeps_stored_credentials_and_query() -> None:
    _store(STORED)
    out = _put(redis_url=MASKED, csp_enforce=True)
    assert _saved() == STORED
    assert out["redis_url"] == MASKED
    assert (read_json("app") or {})["CSP_ENFORCE"] is True


def test_empty_or_missing_redis_url_keeps_the_stored_value() -> None:
    _store(STORED)
    _put(redis_url="   ", csp_enforce=True)
    assert _saved() == STORED
    _put(rate_limit_enabled=False)
    assert _saved() == STORED


def test_clear_flag_disables_redis_even_when_a_value_is_sent() -> None:
    _store(STORED)
    out = _put(redis_url=MASKED, clear_redis_url=True)
    assert _saved() == ""
    assert (out["redis_url"], out["redis_url_set"], out["redis_password_set"]) == ("", False, False)


def test_same_server_with_another_db_keeps_credentials() -> None:
    _store(STORED)
    _put(redis_url="redis://cache.internal:6380/7")
    assert _saved() == "redis://:s3cret@cache.internal:6380/7?ssl_cert_reqs=none"


@pytest.mark.parametrize(
    "submitted",
    ["redis://attacker.example:6380/2", "redis://cache.internal:6381/2", "redis://cache.internal/2"],
)
def test_another_host_or_port_never_inherits_the_stored_password(submitted: str) -> None:
    _store(STORED)
    _put(redis_url=submitted)
    assert _saved() == submitted


@pytest.mark.parametrize(
    "submitted",
    [
        "redis://:n3w-secret@cache.internal:6380/2",
        "redis://cache.internal:6380/2?health_check_interval=10",
    ],
)
def test_explicit_credentials_or_query_replace_the_stored_ones(submitted: str) -> None:
    _store(STORED)
    _put(redis_url=submitted)
    assert _saved() == submitted


def test_env_locked_redis_accepts_its_own_masked_value_back(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", STORED)
    get_settings.cache_clear()
    out = get_runtime_env(ADMIN)
    assert out["redis_url"] == MASKED
    assert "redis_url" in out["env_locked"]
    _put(redis_url=MASKED, csp_enforce=True)
    saved = read_json("app") or {}
    assert "REDIS_URL" not in saved
    assert saved["CSP_ENFORCE"] is True


@pytest.mark.parametrize(
    "fields",
    [{"redis_url": "redis://attacker.example:6380/2"}, {"clear_redis_url": True}],
)
def test_env_locked_redis_refuses_changes(monkeypatch, fields: dict) -> None:
    monkeypatch.setenv("REDIS_URL", STORED)
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        _put(**fields)
    assert exc.value.status_code == 409
    assert "REDIS_URL" in exc.value.detail
    assert not read_json("app")


def test_connection_test_fills_in_stored_credentials_only_for_the_same_server(monkeypatch) -> None:
    _store(STORED)
    probed: list[str] = []

    def _probe(url: str):
        probed.append(url)
        return SimpleNamespace(ok=True, message="ok", latency_ms=1.0)

    monkeypatch.setattr("app.services.runtime_health.probe_redis_url", _probe)
    for submitted in (MASKED, "", "redis://attacker.example:6380/2"):
        probe_runtime_redis(RuntimeRedisTestIn(redis_url=submitted), ADMIN)
    assert probed == [STORED, STORED, "redis://attacker.example:6380/2"]
