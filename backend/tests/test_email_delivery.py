"""邮件验证码投递模式；失败日志脱敏并按故障类型去重；不加密时只对本机中继做 SMTP AUTH。"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable
from typing import Any

import pytest

from app.core.biz_logging import clear_log_until_change
from app.core.config import get_settings
from app.services import email as email_service
from app.services.email import _send_with_config
from app.services.email_config import is_loopback_host, plaintext_auth_error
from app.services.security_bootstrap import check_email_code_log_policy

_LOGGER = "app.services.email"
_CODE = "482913"
_PASSWORD = "smtp-pw-secret"
_CFG = {
    "enabled": True,
    "smtp_host": "smtp.example.com",
    "smtp_port": 465,
    "smtp_user": "bot@example.com",
    "smtp_from": "bot@example.com",
    "smtp_password": _PASSWORD,
    "encryption": "SSL",
    "code_expire_minutes": 15,
}


@pytest.fixture(autouse=True)
def _fresh_email_log_dedupe():
    for key in email_service._LOG_KEYS:
        clear_log_until_change(key)
    yield
    for key in email_service._LOG_KEYS:
        clear_log_until_change(key)


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.fail: Callable[[str], BaseException] | None = None


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()

    class _Server:
        def __init__(self, host: str, port: int, **_kwargs: Any) -> None:
            rec.calls.append(("connect", host, port))

        def __enter__(self) -> _Server:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def ehlo(self) -> None:
            rec.calls.append(("ehlo",))

        def starttls(self, **_kwargs: Any) -> None:
            rec.calls.append(("starttls",))

        def login(self, user: str, password: str) -> None:
            rec.calls.append(("login", user, password))

        def send_message(self, msg: Any) -> None:
            rec.calls.append(("send", str(msg["To"])))
            if rec.fail is not None:
                raise rec.fail(str(msg["To"]))

    monkeypatch.setattr(email_service.smtplib, "SMTP", _Server)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", _Server)
    return rec


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == _LOGGER and r.levelno >= logging.WARNING
    ]


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


def test_log_mode_when_allowed(monkeypatch, caplog) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "true")
    get_settings.cache_clear()
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    out = _send_with_config(
        {"enabled": False, "smtp_host": "", "code_expire_minutes": 15},
        "alice@example.com",
        "654321",
    )
    get_settings.cache_clear()
    assert out["mode"] == "log"
    assert "alice@example.com" not in caplog.text
    assert "a***@example.com → 654321" in caplog.text


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


def test_smtp_exception_is_smtp_error_not_log(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "false")
    get_settings.cache_clear()

    class _Boom:
        def __init__(self, *_a, **_k):
            raise OSError("smtp down")

    monkeypatch.setattr("app.services.email.smtplib.SMTP_SSL", _Boom)
    out = _send_with_config(
        {
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_user": "u@example.com",
            "smtp_from": "u@example.com",
            "smtp_password": "secret",
            "encryption": "SSL",
            "code_expire_minutes": 15,
        },
        "a@b.com",
        "111111",
    )
    get_settings.cache_clear()
    assert out["sent"] is False
    assert out["mode"] == "smtp_error"


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


@pytest.mark.parametrize(
    ("addr", "masked"),
    [
        ("alice@example.com", "a***@example.com"),
        (" Bob.Smith+tag@mail.example.org ", "B***@mail.example.org"),
        ("@example.com", "***@example.com"),
        ("not-an-email", "***"),
        ("", "***"),
    ],
)
def test_mask_email(addr: str, masked: str) -> None:
    assert email_service._mask_email(addr) == masked


def test_unavailable_warns_once_without_recipient(monkeypatch, caplog) -> None:
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "false")
    get_settings.cache_clear()
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    for to in ("alice@example.com", "bob@example.com", "carol@example.org"):
        out = _send_with_config({**_CFG, "enabled": False}, to, _CODE)
        assert out == {"sent": False, "mode": "unavailable"}
    assert _warnings(caplog) == ["邮件未配置且未开启 ALLOW_EMAIL_CODE_LOG，无法发送验证码"]
    for to in ("alice@example.com", "bob@example.com", "carol@example.org"):
        assert to not in caplog.text
    assert "c***@example.org" in caplog.text
    assert _CODE not in caplog.text


def test_smtp_failures_warn_once_per_kind_without_recipients(smtp, caplog) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    smtp.fail = lambda to: smtplib.SMTPRecipientsRefused(
        {to: (550, f"5.1.1 <{to}>: Recipient address rejected".encode())}
    )
    recipients = ("alice@example.com", "bob@example.com", "carol@example.org")
    for to in recipients:
        assert _send_with_config(_CFG, to, _CODE) == {"sent": False, "mode": "smtp_error"}

    assert _warnings(caplog) == [
        "发送验证邮件失败 host=smtp.example.com port=465 encryption=SSL "
        "error=SMTPRecipientsRefused"
    ]
    assert all(r.exc_info is None for r in caplog.records)
    for to in recipients:
        assert to not in caplog.text
    for masked in ("a***@example.com", "b***@example.com", "c***@example.org"):
        assert f"to={masked}" in caplog.text
    assert _CODE not in caplog.text
    assert _PASSWORD not in caplog.text


def test_new_failure_kind_or_success_rearms_the_warning(smtp, caplog) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    smtp.fail = lambda _to: OSError("smtp down")
    for _ in range(3):
        _send_with_config(_CFG, "alice@example.com", _CODE)
    smtp.fail = lambda _to: smtplib.SMTPAuthenticationError(
        535, b"5.7.8 bot@example.com: authentication failed"
    )
    for _ in range(2):
        _send_with_config(_CFG, "alice@example.com", _CODE)
    smtp.fail = None
    assert _send_with_config(_CFG, "alice@example.com", _CODE) == {"sent": True, "mode": "smtp"}
    smtp.fail = lambda _to: smtplib.SMTPAuthenticationError(535, b"5.7.8 rejected")
    _send_with_config(_CFG, "alice@example.com", _CODE)

    prefix = "发送验证邮件失败 host=smtp.example.com port=465 encryption=SSL error="
    assert _warnings(caplog) == [
        prefix + "OSError: smtp down",
        prefix + "SMTPAuthenticationError 535",
        prefix + "SMTPAuthenticationError 535",
    ]
    assert "authentication failed" not in caplog.text


@pytest.mark.parametrize("encryption", ["NONE", "none", "TLS"])
def test_plaintext_auth_to_remote_host_is_refused_before_connecting(
    smtp, caplog, encryption: str
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    cfg = {**_CFG, "smtp_port": 25, "encryption": encryption}
    for to in ("alice@example.com", "bob@example.com"):
        assert _send_with_config(cfg, to, _CODE) == {"sent": False, "mode": "smtp_error"}
    assert smtp.calls == []
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "host=smtp.example.com port=25" in warnings[0]
    assert plaintext_auth_error("smtp.example.com", encryption) in warnings[0]
    assert _PASSWORD not in caplog.text


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_plaintext_auth_to_loopback_relay_still_sends(smtp, host: str) -> None:
    cfg = {**_CFG, "smtp_host": host, "smtp_port": 25, "encryption": "NONE"}
    assert _send_with_config(cfg, "alice@example.com", _CODE) == {"sent": True, "mode": "smtp"}
    assert smtp.calls == [
        ("connect", host, 25),
        ("ehlo",),
        ("login", "bot@example.com", _PASSWORD),
        ("send", "alice@example.com"),
    ]


def test_starttls_upgrades_before_auth(smtp) -> None:
    cfg = {**_CFG, "smtp_port": 587, "encryption": "STARTTLS"}
    assert _send_with_config(cfg, "alice@example.com", _CODE) == {"sent": True, "mode": "smtp"}
    assert smtp.calls == [
        ("connect", "smtp.example.com", 587),
        ("ehlo",),
        ("starttls",),
        ("ehlo",),
        ("login", "bot@example.com", _PASSWORD),
        ("send", "alice@example.com"),
    ]


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("localhost", True),
        (" LocalHost ", True),
        ("127.0.0.1", True),
        ("127.8.9.10", True),
        ("::1", True),
        ("[::1]", True),
        ("::ffff:127.0.0.1", True),
        ("", False),
        ("smtp.example.com", False),
        ("localhost.example.com", False),
        ("mail.localhost", False),
        ("127.0.0.1.nip.io", False),
        ("10.0.0.1", False),
        ("0.0.0.0", False),
        ("::", False),
        ("::ffff:10.0.0.1", False),
    ],
)
def test_is_loopback_host_only_trusts_literals(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected


def test_plaintext_auth_error_only_for_remote_plaintext() -> None:
    assert plaintext_auth_error("smtp.example.com", "SSL") is None
    assert plaintext_auth_error("smtp.example.com", "starttls") is None
    assert plaintext_auth_error("127.0.0.1", "NONE") is None
    refusal = plaintext_auth_error("smtp.example.com", "NONE")
    assert refusal is not None
    assert "SSL" in refusal and "STARTTLS" in refusal
    assert plaintext_auth_error("smtp.example.com", "") == refusal
