"""发码 / 验码接口对已注册与未注册邮箱给出完全一样的响应；已注册邮箱收提醒信而不是验证码。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.auth import router as auth_router
from app.api.auth.helpers import PURPOSE_REGISTER, PURPOSE_RESET
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import create_user_access_token, hash_password, verify_password
from app.core.session_cookies import ACCESS_COOKIE
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.services.email import (
    NOTICE_ALREADY_REGISTERED,
    NOTICE_BIND_TAKEN,
    NOTICE_NO_ACCOUNT_RESET,
)
from app.services.email_config import save_email_config

TAKEN = "taken@example.com"
FRESH = "fresh@example.com"
PASSWORD = "Str0ng-Enough!"
NEW_PASSWORD = "Brand-New-Passw0rd"
WRONG_CODE = "abcdef"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("ALLOW_EMAIL_CODE_LOG", "false")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    def _db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    api = FastAPI()
    api.include_router(auth_router, prefix="/api")
    api.dependency_overrides[get_db] = _db
    with SessionLocal() as db:
        db.add(
            User(
                username="taken",
                email=TAKEN,
                display_name="taken",
                password_hash=hash_password(PASSWORD),
                role=UserRole.user,
                email_verified=True,
            )
        )
        binder = User(
            username="qq_binder",
            email=None,
            display_name="qq",
            password_hash=hash_password("Unused-Passw0rd"),
            role=UserRole.user,
            email_verified=True,
        )
        db.add(binder)
        db.commit()
        token = create_user_access_token(binder)

    mail: dict[str, list[tuple[str, str]]] = {"codes": [], "notices": []}

    def _code(to: str, code: str, **_kw) -> dict:
        mail["codes"].append((to, code))
        return {"sent": True, "mode": "smtp"}

    def _notice(to: str, kind: str, **_kw) -> dict:
        mail["notices"].append((to, kind))
        return {"sent": True, "mode": "smtp"}

    monkeypatch.setattr("app.api.auth.helpers.send_verification_email", _code)
    monkeypatch.setattr("app.api.auth.helpers.send_notice_email", _notice)
    yield SimpleNamespace(
        client=TestClient(api),
        SessionLocal=SessionLocal,
        bearer={"Authorization": f"Bearer {token}"},
        mail=mail,
    )
    engine.dispose()
    get_settings.cache_clear()


def _smtp_configured() -> None:
    save_email_config(
        None,
        {
            "enabled": True,
            "smtp_user": "bot@example.com",
            "smtp_from": "bot@example.com",
            "smtp_password": "app-password",
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "encryption": "SSL",
            "code_expire_minutes": 10,
        },
    )


def _shape(resp) -> tuple[int, object]:
    """去掉回显的邮箱本身，其余（状态码、文案、delivery）必须逐字相同。"""
    body = resp.json()
    if isinstance(body, dict) and "email" in body:
        body = {**body, "email": "<echo>"}
    return resp.status_code, body


def _stored_code(env, email: str, purpose: str) -> str:
    with env.SessionLocal() as db:
        row = (
            db.query(RegisterChallenge)
            .filter(RegisterChallenge.email == email, RegisterChallenge.purpose == purpose)
            .one()
        )
        return row.code


SENDERS = {
    "send-register-code": "/api/auth/send-register-code",
    "resend-code": "/api/auth/resend-code",
    "send-reset-password-code": "/api/auth/send-reset-password-code",
    "send-bind-email-code": "/api/auth/send-bind-email-code",
}


def _send(env, name: str, email: str):
    headers = env.bearer if name == "send-bind-email-code" else None
    return env.client.post(SENDERS[name], json={"email": email}, headers=headers)


@pytest.mark.parametrize(
    "name,taken_notice,fresh_notice",
    [
        ("send-register-code", NOTICE_ALREADY_REGISTERED, None),
        ("resend-code", NOTICE_ALREADY_REGISTERED, None),
        ("send-reset-password-code", None, NOTICE_NO_ACCOUNT_RESET),
        ("send-bind-email-code", NOTICE_BIND_TAKEN, None),
    ],
)
def test_send_code_responses_do_not_reveal_registration(env, name, taken_notice, fresh_notice) -> None:
    _smtp_configured()
    taken = _send(env, name, TAKEN)
    fresh = _send(env, name, FRESH)
    assert taken.status_code == 200, taken.text
    assert _shape(taken) == _shape(fresh)
    assert taken.json()["delivery"] == "smtp"

    expected_notices = [(e, n) for e, n in ((TAKEN, taken_notice), (FRESH, fresh_notice)) if n]
    assert env.mail["notices"] == expected_notices
    coded = [to for to, _code in env.mail["codes"]]
    assert coded == [e for e, n in ((TAKEN, taken_notice), (FRESH, fresh_notice)) if not n]


@pytest.mark.parametrize("name", sorted(SENDERS))
def test_unconfigured_smtp_fails_the_same_for_every_address(env, name) -> None:
    taken = _send(env, name, TAKEN)
    fresh = _send(env, name, FRESH)
    assert taken.status_code == 503
    assert _shape(taken) == _shape(fresh)
    assert env.mail == {"codes": [], "notices": []}


VERIFIERS = {
    "register": ("/api/auth/register", {"password": NEW_PASSWORD}, "send-register-code"),
    "verify-email": ("/api/auth/verify-email", {}, "send-register-code"),
    "reset-password": ("/api/auth/reset-password", {"new_password": NEW_PASSWORD}, "send-reset-password-code"),
    "bind-email": ("/api/auth/bind-email", {}, "send-bind-email-code"),
}


def _verify(env, name: str, email: str, code: str):
    path, extra, _sender = VERIFIERS[name]
    headers = env.bearer if name == "bind-email" else None
    return env.client.post(path, json={"email": email, "code": code, **extra}, headers=headers)


@pytest.mark.parametrize("requested_code", [True, False])
@pytest.mark.parametrize("name", sorted(VERIFIERS))
def test_wrong_code_errors_do_not_reveal_registration(env, name, requested_code) -> None:
    _smtp_configured()
    if requested_code:
        sender = VERIFIERS[name][2]
        assert _send(env, sender, TAKEN).status_code == 200
        assert _send(env, sender, FRESH).status_code == 200
    taken = _verify(env, name, TAKEN, WRONG_CODE)
    fresh = _verify(env, name, FRESH, WRONG_CODE)
    assert taken.status_code == 400
    assert _shape(taken) == _shape(fresh)


def test_register_checks_the_code_before_the_existing_account(env) -> None:
    _smtp_configured()
    _send(env, "send-register-code", TAKEN)
    assert env.mail["codes"] == []
    assert _verify(env, "register", TAKEN, WRONG_CODE).json()["detail"] == "验证码错误"
    stored = _stored_code(env, TAKEN, PURPOSE_REGISTER)
    resp = _verify(env, "register", TAKEN, stored)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "邮箱已被注册"
    with env.SessionLocal() as db:
        assert db.query(RegisterChallenge).count() == 0
        assert db.query(User).filter(User.email == TAKEN).count() == 1


def test_fresh_email_registers_with_its_code_and_gets_a_cookie_session(env) -> None:
    _smtp_configured()
    _send(env, "send-register-code", FRESH)
    [(to, code)] = env.mail["codes"]
    assert to == FRESH
    resp = _verify(env, "register", FRESH, code)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"message": "注册成功", "email": FRESH, "delivery": None}
    assert env.client.cookies.get(ACCESS_COOKIE)


def test_verify_email_without_account_is_generic_and_keeps_the_code(env) -> None:
    _smtp_configured()
    _send(env, "send-register-code", FRESH)
    [(_to, code)] = env.mail["codes"]
    resp = _verify(env, "verify-email", FRESH, code)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "验证失败，请检查邮箱与验证码"
    assert _verify(env, "register", FRESH, code).status_code == 200


def test_reset_for_unknown_email_fails_generically_even_with_the_stored_code(env) -> None:
    _smtp_configured()
    _send(env, "send-reset-password-code", FRESH)
    stored = _stored_code(env, FRESH, PURPOSE_RESET)
    resp = _verify(env, "reset-password", FRESH, stored)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "重置失败，请检查邮箱与验证码"

    _send(env, "send-reset-password-code", TAKEN)
    [(to, code)] = env.mail["codes"]
    assert to == TAKEN
    assert _verify(env, "reset-password", TAKEN, code).status_code == 200
    with env.SessionLocal() as db:
        user = db.query(User).filter(User.email == TAKEN).one()
        assert verify_password(NEW_PASSWORD, user.password_hash)
        assert db.query(User).filter(User.email == FRESH).count() == 0


@pytest.mark.parametrize(
    "name,field,email",
    [
        ("register", "password", FRESH),
        ("reset-password", "new_password", TAKEN),
        ("bind-email", "password", FRESH),
    ],
)
def test_overlong_password_is_refused_before_the_code_is_spent(env, name, field, email) -> None:
    _smtp_configured()
    path, extra, sender = VERIFIERS[name]
    assert _send(env, sender, email).status_code == 200
    [(_to, code)] = env.mail["codes"]
    headers = env.bearer if name == "bind-email" else None
    body = {"email": email, "code": code, **extra}
    # 9 + 22×3 = 75 字节，字符数远没到 256 的输入上限
    resp = env.client.post(path, json={**body, field: "Passw0rd-" + "密" * 22}, headers=headers)
    assert resp.status_code == 400
    assert "最多 72 字节" in resp.json()["detail"]
    retry = env.client.post(path, json={**body, field: NEW_PASSWORD}, headers=headers)
    assert retry.status_code == 200, retry.text


def test_bind_taken_email_is_refused_after_the_code_check(env) -> None:
    _smtp_configured()
    _send(env, "send-bind-email-code", TAKEN)
    stored = _stored_code(env, TAKEN, "bind")
    resp = _verify(env, "bind-email", TAKEN, stored)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "该邮箱已被其他账号使用"
    with env.SessionLocal() as db:
        assert db.query(User).filter(User.username == "qq_binder").one().email is None
