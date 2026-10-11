"""会话：token_version 吊销（退出所有设备 / 改密 / 重置）、Cookie 会话的 CSRF、登录失败退避。"""

from __future__ import annotations

import warnings
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.security as security
import app.models  # noqa: F401
from app.api.auth import router as auth_router
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.deps import get_current_user, get_optional_user
from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
from app.core.rate_limit import LOGIN_FAILURES_BEFORE_LOCK, reset_rate_limits_for_tests
from app.core.security import create_user_access_token, hash_password
from app.core.session_cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.core.timeutil import now_naive
from app.models.member import Member
from app.models.mihoyo import MihoyoBind
from app.models.user import User, UserRole
from app.services.email import NOTICE_QQ_LINKED
from app.services.member_sync import delete_user_with_member, ensure_user_member
from app.services.oauth_ticket import issue_oauth_ticket

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


def test_change_password_refuses_more_than_72_bytes(env) -> None:
    api, _, _ = env
    client = TestClient(api)
    _login(client)
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Passw0rd-" + "密" * 22},
        headers=_csrf(client),
    )
    assert resp.status_code == 400
    assert "最多 72 字节" in resp.json()["detail"]
    assert _login(TestClient(api)).status_code == 200


def test_change_username_reissues_the_cookie_without_a_token_in_the_body(env) -> None:
    api, _, uid = env
    client = TestClient(api)
    _login(client)
    before = client.cookies.get(ACCESS_COOKIE)
    resp = client.post(
        "/api/auth/change-username",
        json={"new_username": "alice_two", "current_password": PASSWORD},
        headers=_csrf(client),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "message": "用户名已更新", "username": "alice_two"}
    assert client.cookies.get(ACCESS_COOKIE) not in (None, before)
    assert client.get("/r").json() == {"id": uid}


def test_qq_exchange_sets_the_cookie_once_and_returns_no_token(env) -> None:
    api, SessionLocal, uid = env
    with SessionLocal() as db:
        user = db.get(User, uid)
        ticket = issue_oauth_ticket(db, create_user_access_token(user))
        db.commit()
    client = TestClient(api)
    resp = client.post("/api/auth/qq/exchange", json={"ticket": ticket})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "message": "登录成功"}
    assert client.get("/r").json() == {"id": uid}

    again = TestClient(api).post("/api/auth/qq/exchange", json={"ticket": ticket})
    assert again.status_code == 400
    assert again.json()["detail"] == "换票码无效或已使用"


def test_reset_password_revokes_sessions_and_lifts_login_lock(env, monkeypatch) -> None:
    api, _, uid = env
    sent: list[str] = []

    def _capture(_email, code, **_kw):
        sent.append(code)
        return {"sent": True, "mode": "smtp"}

    monkeypatch.setattr("app.api.auth.helpers.send_verification_email", _capture)
    monkeypatch.setattr("app.api.auth.helpers.precheck_email_delivery", lambda _cfg: "smtp")
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


def _trust_forwarded_for(monkeypatch) -> None:
    monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "true")
    get_settings.cache_clear()


def test_attacker_lock_does_not_block_owner_on_another_ip(env, monkeypatch) -> None:
    api, _, uid = env
    _trust_forwarded_for(monkeypatch)
    attacker = TestClient(api, headers={"X-Forwarded-For": "203.0.113.66"})
    owner = TestClient(api, headers={"X-Forwarded-For": "198.51.100.10"})
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 3):
        attacker.post("/api/auth/login", json={"username": "alice", "password": "nope-nope"})
    assert _login(attacker).status_code == 429
    assert _login(owner).status_code == 200
    assert owner.get("/r").json() == {"id": uid}


def test_login_body_carries_no_token(env) -> None:
    api, _, _ = env
    client = TestClient(api)
    resp = _login(client)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "message": "登录成功"}
    assert client.cookies.get(ACCESS_COOKIE)


@pytest.mark.parametrize(
    "username,password",
    [("a" * 129, PASSWORD), ("alice", "x" * 257), ("", PASSWORD), ("alice", "")],
)
def test_login_rejects_out_of_bounds_input(env, username, password) -> None:
    api, _, _ = env
    resp = TestClient(api).post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 422


def _count_bcrypt(monkeypatch) -> list[bytes]:
    seen: list[bytes] = []
    real = security.bcrypt.checkpw

    def _spy(password: bytes, hashed: bytes) -> bool:
        seen.append(hashed)
        return real(password, hashed)

    monkeypatch.setattr(security.bcrypt, "checkpw", _spy)
    return seen


def test_unknown_account_costs_the_same_bcrypt_as_wrong_password(env, monkeypatch) -> None:
    api, _, _ = env
    client = TestClient(api)
    seen = _count_bcrypt(monkeypatch)
    unknown = _login(client, "wrong-password", "nobody@example.com")
    unknown_checks = len(seen)
    wrong = _login(client, "wrong-password", EMAIL)
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert unknown_checks == 1
    assert len(seen) == 2


def _qq_temp_user(SessionLocal, *, mihoyo: bool = False) -> tuple[int, str]:
    with SessionLocal() as db:
        temp = User(
            username="qq_tmp",
            email=None,
            display_name="QQ 小号",
            password_hash=hash_password("temp-account-unused-1"),
            role=UserRole.user,
            email_verified=False,
        )
        db.add(temp)
        db.flush()
        member = ensure_user_member(db, temp)
        member.qq_openid = "OPENID-TEMP"
        member.qq_nickname = "qq-nick"
        if mihoyo:
            db.add(MihoyoBind(member_id=member.id, credentials_enc="x"))
        db.commit()
        return temp.id, create_user_access_token(temp)


def _link(client: TestClient, token: str, password: str, email: str = EMAIL):
    return client.post(
        "/api/auth/link-existing-account",
        json={"email": email, "password": password},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_link_existing_shares_the_login_lock(env, monkeypatch) -> None:
    api, SessionLocal, _ = env
    monkeypatch.setattr("app.api.auth.email_bind.notify_account_event", lambda *_a: None)
    _, token = _qq_temp_user(SessionLocal)
    client = TestClient(api)
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        resp = _link(client, token, "wrong-password")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "邮箱或密码错误"
    assert _link(client, token, PASSWORD).status_code == 429
    assert _login(client, PASSWORD, EMAIL).status_code == 429


def test_login_failures_also_lock_link_existing(env) -> None:
    api, SessionLocal, _ = env
    _, token = _qq_temp_user(SessionLocal)
    client = TestClient(api)
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        assert _login(client, "wrong-password", EMAIL).status_code == 401
    assert _link(client, token, PASSWORD).status_code == 429


def test_link_existing_unknown_email_runs_bcrypt_like_wrong_password(env, monkeypatch) -> None:
    api, SessionLocal, _ = env
    _, token = _qq_temp_user(SessionLocal)
    client = TestClient(api)
    seen = _count_bcrypt(monkeypatch)
    unknown = _link(client, token, "wrong-password", "nobody@example.com")
    assert len(seen) == 1
    wrong = _link(client, token, "wrong-password")
    assert len(seen) == 2
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_link_existing_merges_notifies_target_and_sets_cookie_only(env, monkeypatch) -> None:
    api, SessionLocal, uid = env
    notified: list[tuple] = []
    monkeypatch.setattr(
        "app.api.auth.email_bind.notify_account_event",
        lambda *args: notified.append(args),
    )
    temp_id, token = _qq_temp_user(SessionLocal)
    client = TestClient(api)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        resp = _link(client, token, PASSWORD)
    sa_warnings = [str(w.message) for w in caught if issubclass(w.category, SAWarning)]
    assert sa_warnings == []
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" not in body and "token_type" not in body
    assert body["user"]["id"] == uid
    assert notified == [(EMAIL, NOTICE_QQ_LINKED)]
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.get("/r").json() == {"id": uid}
    with SessionLocal() as db:
        assert db.get(User, temp_id) is None
        assert db.query(Member).filter(Member.user_id == temp_id).count() == 0
        member = db.query(Member).filter(Member.user_id == uid).one()
        assert member.qq_openid == "OPENID-TEMP"


def test_link_existing_refuses_temp_account_with_mihoyo_bind(env, monkeypatch) -> None:
    api, SessionLocal, _ = env
    notified: list[tuple] = []
    monkeypatch.setattr(
        "app.api.auth.email_bind.notify_account_event",
        lambda *args: notified.append(args),
    )
    temp_id, token = _qq_temp_user(SessionLocal, mihoyo=True)
    resp = _link(TestClient(api), token, PASSWORD)
    assert resp.status_code == 400
    assert "其他平台" in resp.json()["detail"]
    assert notified == []
    with SessionLocal() as db:
        assert db.get(User, temp_id) is not None
        assert db.query(MihoyoBind).count() == 1


def test_token_of_a_deleted_user_does_not_open_a_recycled_id(env, monkeypatch) -> None:
    """SQLite 旧库（建表时没有 AUTOINCREMENT）删掉最新的用户后，下一个注册的人会拿到同一个 id。"""
    api, SessionLocal, _ = env
    real_utc_now = security.utc_now
    with SessionLocal() as db:
        gone = User(
            username="gone",
            email="gone@example.com",
            display_name="gone",
            password_hash=hash_password(PASSWORD),
            role=UserRole.user,
            created_at=now_naive() - timedelta(days=1),
        )
        db.add(gone)
        db.flush()
        ensure_user_member(db, gone)
        db.commit()
        gone_id = gone.id
        with monkeypatch.context() as m:
            m.setattr(security, "utc_now", lambda: real_utc_now() - timedelta(minutes=1))
            stale = {"Authorization": f"Bearer {create_user_access_token(gone)}"}
    client = TestClient(api)
    assert client.get("/r", headers=stale).json() == {"id": gone_id}

    with SessionLocal() as db:
        delete_user_with_member(db, db.get(User, gone_id))
        db.add(
            User(
                id=gone_id,
                username="newcomer",
                email="newcomer@example.com",
                display_name="newcomer",
                password_hash=hash_password(PASSWORD),
                role=UserRole.user,
            )
        )
        db.commit()
        fresh = {"Authorization": f"Bearer {create_user_access_token(db.get(User, gone_id))}"}
    assert client.get("/r", headers=stale).status_code == 401
    assert client.get("/r", headers=fresh).json() == {"id": gone_id}
