"""运行环境设置：环境变量设定的字段只读；PUT 改它们返回 409，原样带回则跳过不写。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.settings import RuntimeEnvUpdate, get_runtime_env, update_runtime_env
from app.core.config import get_settings
from app.core.file_config import read_json

_ENV_NAMES = (
    "APP_ENV",
    "REDIS_URL",
    "CORS_ORIGINS",
    "CORS_ORIGIN_REGEX",
    "CSP_ENFORCE",
    "TRUST_X_FORWARDED_FOR",
    "RATE_LIMIT_ENABLED",
    "DATABASE_URL",
)
ADMIN = object()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _env(monkeypatch, **values: str) -> None:
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def test_nothing_locked_without_env_overrides() -> None:
    out = get_runtime_env(ADMIN)
    assert out["env_locked"] == []
    assert out["rate_limit_enabled"] is True


def test_env_set_fields_are_reported_locked(monkeypatch, tmp_path) -> None:
    _env(
        monkeypatch,
        TRUST_X_FORWARDED_FOR="true",
        DATABASE_URL=f"sqlite:///{tmp_path / 'env.sqlite'}",
    )
    locked = set(get_runtime_env(ADMIN)["env_locked"])
    assert "trust_x_forwarded_for" in locked
    assert {"db_engine", "db_path", "db_url"} <= locked
    assert "app_env" not in locked


def test_changing_env_locked_field_is_rejected(monkeypatch) -> None:
    _env(monkeypatch, TRUST_X_FORWARDED_FOR="true")
    with pytest.raises(HTTPException) as exc:
        update_runtime_env(
            RuntimeEnvUpdate(trust_x_forwarded_for=False, csp_enforce=True), ADMIN
        )
    assert exc.value.status_code == 409
    assert "TRUST_X_FORWARDED_FOR" in exc.value.detail
    assert not read_json("app")


def test_unchanged_locked_field_is_skipped(monkeypatch) -> None:
    _env(monkeypatch, TRUST_X_FORWARDED_FOR="true", APP_ENV="Production")
    out = update_runtime_env(
        RuntimeEnvUpdate(
            trust_x_forwarded_for=True, app_env="production", rate_limit_enabled=False
        ),
        ADMIN,
    )
    saved = read_json("app") or {}
    assert "TRUST_X_FORWARDED_FOR" not in saved
    assert "APP_ENV" not in saved
    assert saved["RATE_LIMIT_ENABLED"] is False
    assert out["restart_required"] is True


def test_database_url_env_locks_database_fields(monkeypatch, tmp_path) -> None:
    _env(monkeypatch, DATABASE_URL=f"sqlite:///{tmp_path / 'env.sqlite'}")
    with pytest.raises(HTTPException) as exc:
        update_runtime_env(
            RuntimeEnvUpdate(db_engine="mysql", db_url="mysql+pymysql://u:p@db/zhange"),
            ADMIN,
        )
    assert exc.value.status_code == 409
    assert "DATABASE_URL" in exc.value.detail
    assert not read_json("database")
