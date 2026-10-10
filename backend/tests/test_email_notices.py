"""账号提醒信不带验证码、尽力而为（发不出去不抛、不进 WARNING 刷屏）；验证码信写的有效期按 30 分钟封顶。"""

from __future__ import annotations

import logging
import re
from email.message import EmailMessage
from typing import Any

import pytest

from app.core.biz_logging import clear_log_until_change
from app.core.config import get_settings
from app.core.file_config import read_json, write_json
from app.services import email as email_service
from app.services.email import (
    NOTICE_ALREADY_REGISTERED,
    NOTICE_BIND_TAKEN,
    NOTICE_NO_ACCOUNT_RESET,
    NOTICE_QQ_LINKED,
    _send_with_config,
    email_delivery_mode,
    notify_account_event,
    precheck_email_delivery,
    send_notice_email,
)
from app.services.email_config import (
    MAX_CODE_EXPIRE_MINUTES,
    code_expire_minutes,
    load_email_config,
    save_email_config,
)

_LOGGER = "app.services.email"
SMTP = {
    "enabled": True,
    "smtp_user": "bot@example.com",
    "smtp_from": "bot@example.com",
    "smtp_password": "smtp-pw-secret",
    "smtp_host": "smtp.example.com",
    "smtp_port": 465,
    "encryption": "SSL",
    "code_expire_minutes": 15,
}
ALL_NOTICES = [NOTICE_ALREADY_REGISTERED, NOTICE_NO_ACCOUNT_RESET, NOTICE_BIND_TAKEN, NOTICE_QQ_LINKED]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "false")
    get_settings.cache_clear()
    for key in email_service._LOG_KEYS:
        clear_log_until_change(key)
    yield
    for key in email_service._LOG_KEYS:
        clear_log_until_change(key)
    get_settings.cache_clear()


class _Outbox(list):
    fail: BaseException | None = None


@pytest.fixture
def outbox(monkeypatch) -> _Outbox:
    box = _Outbox()

    class _Server:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def __enter__(self) -> _Server:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def ehlo(self) -> None:
            pass

        def starttls(self, **_k: Any) -> None:
            pass

        def login(self, *_a: Any) -> None:
            pass

        def send_message(self, msg: EmailMessage) -> None:
            if box.fail is not None:
                raise box.fail
            box.append(msg)

    monkeypatch.setattr(email_service.smtplib, "SMTP", _Server)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", _Server)
    return box


def _warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == _LOGGER and r.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    "configured,expected",
    [(1440, 30), (31, 30), (30, 30), (10, 10), (-5, 1), (None, 15), ("abc", 15)],
)
def test_code_expiry_is_capped(configured, expected: int) -> None:
    assert MAX_CODE_EXPIRE_MINUTES == 30
    assert code_expire_minutes({"code_expire_minutes": configured}) == expected


def test_code_mail_states_the_capped_expiry(outbox) -> None:
    out = _send_with_config({**SMTP, "code_expire_minutes": 1440}, "alice@example.com", "482913")
    assert out == {"sent": True, "mode": "smtp"}
    [msg] = outbox
    body = msg.get_content()
    assert "482913" in body
    assert "有效期 30 分钟" in body
    assert "1440" not in body


def test_saved_and_hand_edited_expiry_are_both_capped() -> None:
    assert save_email_config(None, {**SMTP, "code_expire_minutes": 600})["code_expire_minutes"] == 30
    assert read_json("email")["code_expire_minutes"] == 30
    write_json("email", {**SMTP, "code_expire_minutes": 600})
    assert load_email_config()["code_expire_minutes"] == 30


@pytest.mark.parametrize("kind", ALL_NOTICES)
def test_notice_mail_has_its_own_subject_and_no_code(outbox, kind: str) -> None:
    save_email_config(None, SMTP)
    assert send_notice_email("alice@example.com", kind) == {"sent": True, "mode": "smtp"}
    [msg] = outbox
    subject, body = email_service._NOTICES[kind]
    assert msg["Subject"] == subject
    assert msg["To"] == "alice@example.com"
    assert msg.get_content().strip() == body
    assert not re.search(r"\d{6}", msg.get_content())


def test_qq_linked_notice_is_sent_when_mail_is_configured(outbox) -> None:
    save_email_config(None, SMTP)
    notify_account_event("owner@example.com", NOTICE_QQ_LINKED)
    [msg] = outbox
    assert msg["To"] == "owner@example.com"
    assert msg["Subject"] == email_service._NOTICES[NOTICE_QQ_LINKED][0]


def test_notify_skips_quietly_without_address_or_mail_setup(outbox, caplog) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    notify_account_event(None, NOTICE_QQ_LINKED)
    notify_account_event("", NOTICE_QQ_LINKED)
    notify_account_event("owner@example.com", NOTICE_QQ_LINKED)
    assert outbox == []
    assert _warnings(caplog) == []


def test_notify_never_raises_and_logs_without_details(monkeypatch, caplog) -> None:
    save_email_config(None, SMTP)

    def _boom(*_a, **_k):
        raise RuntimeError("smtp-pw-secret leaked into a message")

    monkeypatch.setattr(email_service, "send_notice_email", _boom)
    notify_account_event("owner@example.com", NOTICE_QQ_LINKED)
    assert _warnings(caplog) == ["账号提醒邮件发送异常 kind=qq_linked error=RuntimeError"]
    assert "smtp-pw-secret" not in caplog.text
    assert "owner@example.com" not in caplog.text


def test_notify_smtp_failure_is_swallowed_and_masked(outbox, caplog) -> None:
    save_email_config(None, SMTP)
    outbox.fail = OSError("connection reset")
    notify_account_event("owner@example.com", NOTICE_QQ_LINKED)
    assert outbox == []
    [warning] = _warnings(caplog)
    assert warning.startswith("发送提醒邮件失败 host=smtp.example.com")
    assert "owner@example.com" not in caplog.text


@pytest.mark.parametrize(
    "cfg,env,mode",
    [
        (SMTP, {}, "smtp"),
        ({**SMTP, "enabled": False}, {}, "unavailable"),
        ({**SMTP, "smtp_host": ""}, {}, "unavailable"),
        ({**SMTP, "enabled": False}, {"ALLOW_EMAIL_CODE_LOG": "true"}, "log"),
        ({**SMTP, "enabled": False}, {"ALLOW_EMAIL_CODE_LOG": "true", "APP_ENV": "production"}, "unavailable"),
        ({**SMTP, "encryption": "NONE", "smtp_port": 25}, {}, "smtp_error"),
        ({**SMTP, "encryption": "NONE", "smtp_host": "127.0.0.1", "smtp_port": 25}, {}, "smtp"),
    ],
)
def test_delivery_mode_is_predicted_from_config_alone(monkeypatch, outbox, cfg, env, mode) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    assert email_delivery_mode(cfg) == mode
    assert outbox == []


def test_precheck_warns_once_per_fault_and_sends_nothing(outbox, caplog) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    for _ in range(3):
        assert precheck_email_delivery({**SMTP, "enabled": False}) == "unavailable"
    assert precheck_email_delivery(SMTP) == "smtp"
    assert _warnings(caplog) == ["邮件未配置且未开启 ALLOW_EMAIL_CODE_LOG，无法发送验证码"]
    assert outbox == []
