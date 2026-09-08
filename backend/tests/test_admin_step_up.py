"""管理员步进：生产校验验证码，development 跳过。"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.auth.step_up import admin_step_up_required, consume_admin_step_up
from app.core.config import get_settings


def _user(**kwargs) -> MagicMock:
    user = MagicMock()
    user.email = kwargs.get("email", "a@b.c")
    user.email_verified = kwargs.get("email_verified", True)
    return user


def test_development_skips_step_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    try:
        assert admin_step_up_required() is False
        consume_admin_step_up(MagicMock(), _user(email=None, email_verified=False), None)
    finally:
        get_settings.cache_clear()


def test_production_requires_verified_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        assert admin_step_up_required() is True
        with pytest.raises(HTTPException) as exc:
            consume_admin_step_up(MagicMock(), _user(email=None, email_verified=False), "123456")
        assert exc.value.status_code == 400
        assert "邮箱" in str(exc.value.detail)
    finally:
        get_settings.cache_clear()


def test_production_requires_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            consume_admin_step_up(MagicMock(), _user(), None)
        assert exc.value.status_code == 400
        assert "验证码" in str(exc.value.detail)
    finally:
        get_settings.cache_clear()


def test_production_verify_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    def boom(*_args, **_kwargs) -> None:
        raise HTTPException(status_code=400, detail="验证码错误")

    monkeypatch.setattr("app.api.auth.step_up._consume_register_challenge", boom)
    try:
        user = _user()
        user.id = 424242
        user.email = "stepup-rl@example.test"
        user.email_verified = True
        for _ in range(12):
            with pytest.raises(HTTPException) as exc:
                consume_admin_step_up(MagicMock(), user, "000000")
            assert exc.value.status_code == 400
        with pytest.raises(HTTPException) as exc:
            consume_admin_step_up(MagicMock(), user, "000000")
        assert exc.value.status_code == 429
    finally:
        get_settings.cache_clear()
