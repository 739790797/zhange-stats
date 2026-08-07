"""邮件验证码投递模式。"""

from app.core.config import get_settings
from app.services.email import _send_with_config
from app.services.security_bootstrap import check_email_code_log_policy


def test_unavailable_without_allow_log(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "false")
    get_settings.cache_clear()
    out = _send_with_config(
        {"enabled": False, "smtp_host": "", "code_expire_minutes": 15},
        "a@b.com",
        "123456",
    )
    get_settings.cache_clear()
    assert out["mode"] == "unavailable"
    assert out["sent"] is False


def test_log_mode_when_allowed(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    out = _send_with_config(
        {"enabled": False, "smtp_host": "", "code_expire_minutes": 15},
        "a@b.com",
        "654321",
    )
    get_settings.cache_clear()
    assert out["mode"] == "log"


def test_production_ignores_allow_log_in_send(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    out = _send_with_config(
        {"enabled": False, "smtp_host": "", "code_expire_minutes": 15},
        "a@b.com",
        "654321",
    )
    get_settings.cache_clear()
    assert out["mode"] == "unavailable"


def test_production_rejects_allow_email_code_log_at_boot(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    try:
        check_email_code_log_policy()
        raised = False
    except RuntimeError as e:
        raised = True
        assert "ALLOW_EMAIL_CODE_LOG" in str(e)
    get_settings.cache_clear()
    assert raised
