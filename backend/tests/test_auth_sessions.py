"""会话：token_version 吊销（退出所有设备 / 改密 / 重置）、Cookie 会话的 CSRF、登录失败退避。"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.auth import router as auth_router
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.deps import get_current_user, get_optional_user
from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
from app.core.rate_limit import LOGIN_FAILURES_BEFORE_LOCK, reset_rate_limits_for_tests
from app.core.security import create_user_access_token, hash_password
from app.core.session_cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.models.user import User, UserRole

EMAIL = "alice@example.com"
PASSWORD = "Str0ng-Enough!"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    reset_rate_limits_for_tests()
    reset_ephemeral_kv_for_tests()
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

    @api.get("/r")
    def read(user: User = Depends(get_current_user)) -> dict:
        return {"id": user.id}

    @api.post("/w")
    def write(user: User = Depends(get_current_user)) -> dict:
        return {"id": user.id}

    @api.post("/o")
    def optional(user: User | None = Depends(get_optional_user)) -> dict:
        return {"id": user.id if user else None}

    api.dependency_overrides[get_db] = _db
    with SessionLocal() as db:
        user = User(
            username="alice",
            email=EMAIL,
            display_name="alice",
            password_hash=hash_password(PASSWORD),
            role=UserRole.user,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        uid = user.id
    yield api, SessionLocal, uid
    reset_rate_limits_for_tests()
    reset_ephemeral_kv_for_tests()
    engine.dispose()
    get_settings.cache_clear()


def _login(client: TestClient, password: str = PASSWORD, account: str = "alice"):
    return client.post("/api/auth/login", json={"username": account, "password": password})


def _csrf(client: TestClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get(CSRF_COOKIE) or ""}


def test_cookie_session_writes_need_csrf_header(env) -> None:
    api, _, uid = env
    client = TestClient(api)
    assert _login(client).status_code == 200
    assert client.get("/r").json() == {"id": uid}
    assert client.post("/w").status_code == 403
    assert client.post("/o").status_code == 403
    assert client.post("/w", headers={CSRF_HEADER: "forged"}).status_code == 403
    assert client.post("/w", headers=_csrf(client)).json() == {"id": uid}
    assert client.post("/o", headers=_csrf(client)).json() == {"id": uid}


def test_bearer_and_guest_skip_csrf(env) -> None:
    api, SessionLocal, uid = env
    client = TestClient(api)
    with SessionLocal() as db:
        token = create_user_access_token(db.get(User, uid))
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.post("/w", headers=bearer).json() == {"id": uid}
    assert client.post("/o", headers=bearer).json() == {"id": uid}
    assert client.post("/o").json() == {"id": None}


def test_logout_all_revokes_every_device(env) -> None:
    api, _, uid = env
    here, elsewhere = TestClient(api), TestClient(api)
    assert _login(here).status_code == 200
    assert _login(elsewhere).status_code == 200

    out = here.post("/api/auth/logout-all", headers=_csrf(here))
    assert out.status_code == 200, out.text
    assert here.cookies.get(ACCESS_COOKIE) is None
    assert elsewhere.get("/r").status_code == 401

    assert _login(elsewhere).status_code == 200
    assert elsewhere.get("/r").json() == {"id": uid}


def test_change_password_keeps_this_device_only(env) -> None:
    api, _, uid = env
    here, elsewhere = TestClient(api), TestClient(api)
    _login(here)
    _login(elsewhere)
    resp = here.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "An0ther-Strong!"},
        headers=_csrf(here),
    )
    assert resp.status_code == 200, resp.text
    assert here.get("/r").json() == {"id": uid}
    assert elsewhere.get("/r").status_code == 401


def test_reset_password_revokes_sessions_and_lifts_login_lock(env, monkeypatch) -> None:
    api, _, uid = env
    sent: list[str] = []

    def _capture(_email, code, **_kw):
        sent.append(code)
        return {"sent": True, "mode": "smtp"}

    monkeypatch.setattr("app.api.auth.helpers.send_verification_email", _capture)
    monkeypatch.setattr(
        "app.services.email_config.load_email_config",
        lambda _db: {"code_expire_minutes": 15},
    )
    victim, attacker = TestClient(api), TestClient(api)
    _login(victim)
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        assert _login(attacker, "wrong-password", EMAIL).status_code == 401
    assert _login(victim, PASSWORD, EMAIL).status_code == 429

    assert victim.post("/api/auth/send-reset-password-code", json={"email": EMAIL}).status_code == 200
    resp = victim.post(
        "/api/auth/reset-password",
        json={"email": EMAIL, "code": sent[-1], "new_password": "Brand-New-Passw0rd"},
    )
    assert resp.status_code == 200, resp.text
    assert victim.get("/r").status_code == 401
    assert _login(victim, "Brand-New-Passw0rd", EMAIL).status_code == 200
    assert victim.get("/r").json() == {"id": uid}


def test_repeated_wrong_passwords_lock_even_the_right_one(env) -> None:
    api, _, _ = env
    client = TestClient(api)
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        assert _login(client, "wrong-password").status_code == 401
    locked = _login(client)
    assert locked.status_code == 429
    assert "分钟后再试" in locked.json()["detail"]
