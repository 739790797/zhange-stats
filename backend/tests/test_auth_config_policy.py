"""auth_config 策略合并。"""

from app.services.auth_config import (
    effective_reject_weak_admin_password,
    public_auth_config,
)


def test_effective_reject_follows_production(monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REJECT_WEAK_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    assert effective_reject_weak_admin_password({"reject_weak_admin_password": None})
    get_settings.cache_clear()


def test_effective_reject_explicit_false(monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    assert not effective_reject_weak_admin_password(
        {"reject_weak_admin_password": False}
    )
    get_settings.cache_clear()


def test_public_auth_config_shape() -> None:
    out = public_auth_config(
        {
            "access_token_expire_minutes": 1440,
            "min_password_length": 10,
            "reject_weak_admin_password": True,
            "enforce_single_admin": True,
        }
    )
    assert out["access_token_expire_days"] == 1.0
    assert out["min_password_length"] == 10
    assert out["enforce_single_admin"] is True
    assert out["reject_weak_admin_password_effective"] is True
