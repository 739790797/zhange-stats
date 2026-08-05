"""弱口令检测。"""

from app.core.config import get_settings
from app.services.security_bootstrap import warn_if_weak_admin_password


def test_warn_weak_password_in_development(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_PASSWORD", "123456")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("REJECT_WEAK_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    warn_if_weak_admin_password()  # 仅 warning
    get_settings.cache_clear()


def test_reject_weak_password_explicit(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_PASSWORD", "123456")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("REJECT_WEAK_ADMIN_PASSWORD", "true")
    get_settings.cache_clear()
    try:
        warn_if_weak_admin_password()
        raised = False
    except RuntimeError:
        raised = True
    finally:
        get_settings.cache_clear()
    assert raised


def test_production_defaults_to_reject(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_PASSWORD", "123456")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REJECT_WEAK_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    try:
        warn_if_weak_admin_password()
        raised = False
    except RuntimeError:
        raised = True
    finally:
        get_settings.cache_clear()
    assert raised


def test_production_can_explicitly_allow_warn_only(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_PASSWORD", "123456")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REJECT_WEAK_ADMIN_PASSWORD", "false")
    get_settings.cache_clear()
    warn_if_weak_admin_password()  # 显式关闭拒绝
    get_settings.cache_clear()
