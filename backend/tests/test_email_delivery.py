"""邮件验证码投递模式。"""

from app.core.config import get_settings
from app.services.email import _send_with_config


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
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    out = _send_with_config(
        {"enabled": False, "smtp_host": "", "code_expire_minutes": 15},
        "a@b.com",
        "654321",
    )
    get_settings.cache_clear()
    assert out["mode"] == "log"
