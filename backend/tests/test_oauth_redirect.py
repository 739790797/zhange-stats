"""OAuth 回跳只去白名单前端；QQ state 绑定发起授权的浏览器（nonce Cookie）；Steam 校验 return_to。"""

from __future__ import annotations

import urllib.parse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.public_url import allowed_frontend_base, resolve_frontend_base
from app.core.rate_limit import reset_rate_limits_for_tests
from app.core.security import create_user_access_token, hash_password
from app.core.session_cookies import QQ_OAUTH_NONCE_COOKIE
from app.models.member import Member
from app.models.user import User, UserRole
from app.services.qq_oauth import (
    PURPOSE_BIND,
    PURPOSE_LOGIN,
    QqProfile,
    create_qq_oauth_state,
    decode_qq_oauth_state,
    new_oauth_nonce,
)
from app.services.steam.openid import create_openid_state

SITE = "https://site.example"
EVIL = "https://evil.example"


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    for name in ("PUBLIC_FRONTEND_URL", "PUBLIC_BACKEND_URL", "CORS_ORIGINS", "CORS_ORIGIN_REGEX"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _request(headers: dict[str, str] | None = None, *, base: str = SITE) -> Request:
    parsed = urllib.parse.urlparse(base)
    raw = [(b"host", parsed.netloc.encode())]
    raw += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": parsed.scheme,
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": raw,
            "client": ("127.0.0.1", 1),
            "server": (parsed.hostname, parsed.port or 443),
        }
    )


def test_spoofed_origin_falls_back_to_site(production) -> None:
    req = _request({"origin": EVIL, "referer": f"{EVIL}/x"})
    assert resolve_frontend_base(req) == SITE
    assert allowed_frontend_base(EVIL, req) == ""


def test_referer_inside_allowlist_is_kept(production) -> None:
    assert resolve_frontend_base(_request({"referer": f"{SITE}/login?next=/me"})) == SITE


def test_cors_origins_and_public_frontend_are_allowlisted(production, monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example")
    get_settings.cache_clear()
    req = _request({"origin": "https://app.example"})
    assert resolve_frontend_base(req) == "https://app.example"
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "https://www.example/")
    get_settings.cache_clear()
    assert resolve_frontend_base(req) == "https://www.example"
    assert allowed_frontend_base("https://app.example/x", req) == "https://app.example"
    assert allowed_frontend_base("https://www.example", req) == "https://www.example"


def test_local_vite_origin_allowed_only_outside_production(production, monkeypatch) -> None:
    req = _request({"origin": "http://localhost:5173"}, base="http://127.0.0.1:6130")
    assert resolve_frontend_base(req) == "http://127.0.0.1:6130"
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    assert resolve_frontend_base(req) == "http://localhost:5173"
    assert allowed_frontend_base("http://localhost.evil.example", req) == ""


@pytest.fixture
def oauth_app(production, monkeypatch):
    from app.api.auth import qq_login
    from app.api.profile import qq as profile_qq
    from app.api.profile import steam as profile_steam

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

    def _creds(_db=None):
        return ("101", "app-key")

    monkeypatch.setattr("app.api.auth.qq_login.get_qq_credentials", _creds)
    monkeypatch.setattr("app.services.integrations_config.get_qq_credentials", _creds)
    monkeypatch.setattr(
        "app.api.profile.qq.exchange_code_for_profile",
        lambda _code, backend=None: QqProfile(
            openid="openid-victim", unionid=None, nickname="<img src=x>小明", avatar_url=None
        ),
    )
    reset_rate_limits_for_tests()
    api = FastAPI()
    api.include_router(qq_login.router, prefix="/api/auth")
    api.include_router(profile_qq.router, prefix="/api")
    api.include_router(profile_steam.router, prefix="/api")
    api.dependency_overrides[get_db] = _db
    yield api, SessionLocal
    reset_rate_limits_for_tests()
    engine.dispose()


def _state_from_start(resp) -> str:
    assert resp.status_code == 200, resp.text
    query = urllib.parse.urlparse(resp.json()["url"]).query
    return urllib.parse.parse_qs(query)["state"][0]


def _callback(client: TestClient, path: str, **params: str):
    resp = client.get(path, params=params, follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    return location, urllib.parse.parse_qs(urllib.parse.urlparse(location).query)


def test_login_start_ignores_spoofed_origin_and_sets_nonce_cookie(oauth_app) -> None:
    api, _ = oauth_app
    client = TestClient(api, base_url=SITE)
    resp = client.get("/api/auth/qq/oauth/start", headers={"origin": EVIL})
    state = decode_qq_oauth_state(_state_from_start(resp))
    assert state["frontend"] == SITE
    assert state["purpose"] == PURPOSE_LOGIN
    cookie = resp.headers["set-cookie"].lower()
    assert cookie.startswith(QQ_OAUTH_NONCE_COOKIE)
    for attr in ("httponly", "path=/api/auth/qq", "secure", "samesite=lax"):
        assert attr in cookie


def test_callback_in_another_browser_gets_no_ticket(oauth_app) -> None:
    api, SessionLocal = oauth_app
    attacker = TestClient(api, base_url=SITE)
    state = _state_from_start(attacker.get("/api/auth/qq/oauth/start", headers={"origin": EVIL}))
    victim = TestClient(api, base_url=SITE)
    location, params = _callback(victim, "/api/auth/qq/callback", code="c", state=state)
    assert location.startswith(f"{SITE}/login?")
    assert params["qq_login"] == ["error"]
    assert "ticket" not in params
    with SessionLocal() as db:
        assert db.query(User).count() == 0


def test_callback_in_same_browser_issues_ticket_once(oauth_app) -> None:
    api, SessionLocal = oauth_app
    client = TestClient(api, base_url=SITE)
    state = _state_from_start(client.get("/api/auth/qq/oauth/start"))
    location, params = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert location.startswith(f"{SITE}/login?")
    assert params["qq_login"] == ["ok"]
    assert params["ticket"][0]
    assert params["name"] == ["img src=x小明"]
    assert client.cookies.get(QQ_OAUTH_NONCE_COOKIE) is None

    _again, replay = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert replay["qq_login"] == ["error"]
    assert "ticket" not in replay
    with SessionLocal() as db:
        user = db.query(User).one()
        assert "<" not in user.display_name and ">" not in user.display_name


def test_callback_rechecks_frontend_stored_in_state(oauth_app) -> None:
    api, _ = oauth_app
    client = TestClient(api, base_url=SITE)
    nonce = new_oauth_nonce()
    state = create_qq_oauth_state(purpose=PURPOSE_LOGIN, nonce=nonce, frontend=EVIL, backend=SITE)
    client.cookies.set(QQ_OAUTH_NONCE_COOKIE, nonce, domain="site.example", path="/api/auth/qq")
    location, params = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert location.startswith(f"{SITE}/login?")
    assert params["qq_login"] == ["ok"]


def _bind_target(SessionLocal) -> tuple[int, int, str]:
    with SessionLocal() as db:
        user = User(
            username="alice",
            email="alice@example.com",
            display_name="alice",
            password_hash=hash_password("correct-horse-battery"),
            role=UserRole.user,
            email_verified=True,
        )
        db.add(user)
        db.flush()
        member = Member(nickname="alice", user_id=user.id)
        db.add(member)
        db.commit()
        return user.id, member.id, create_user_access_token(user)


def test_bind_start_and_callback_bound_to_browser(oauth_app) -> None:
    api, SessionLocal = oauth_app
    uid, mid, token = _bind_target(SessionLocal)
    client = TestClient(api, base_url=SITE)
    resp = client.get(
        "/api/profile/qq/oauth/start",
        headers={"origin": EVIL, "authorization": f"Bearer {token}"},
    )
    raw_state = _state_from_start(resp)
    state = decode_qq_oauth_state(raw_state)
    assert state["frontend"] == SITE
    assert state["purpose"] == PURPOSE_BIND

    stranger = TestClient(api, base_url=SITE)
    location, params = _callback(stranger, "/api/auth/qq/callback", code="c", state=raw_state)
    assert location.startswith(f"{SITE}/profile?")
    assert params["qq_bind"] == ["error"]
    with SessionLocal() as db:
        assert db.get(Member, mid).qq_openid is None

    location, params = _callback(client, "/api/auth/qq/callback", code="c", state=raw_state)
    assert params["qq_bind"] == ["ok"]
    with SessionLocal() as db:
        assert db.get(Member, mid).qq_openid == "openid-victim"
        assert db.get(User, uid) is not None


def test_steam_callback_requires_matching_return_to(oauth_app, monkeypatch) -> None:
    api, SessionLocal = oauth_app
    uid, mid, _token = _bind_target(SessionLocal)
    checked: list[dict] = []

    def _verify(query: dict) -> str:
        checked.append(query)
        raise ValueError("Steam 登录校验未通过")

    monkeypatch.setattr("app.api.profile.steam.verify_steam_openid_assertion", _verify)
    state = create_openid_state(user_id=uid, member_id=mid, frontend=EVIL, backend=SITE)
    client = TestClient(api, base_url=SITE)
    path = "/api/profile/steam/openid/callback"

    location, params = _callback(
        client,
        path,
        state=state,
        **{"openid.mode": "id_res", "openid.return_to": f"{EVIL}/cb?state={state}"},
    )
    assert location.startswith(f"{SITE}/profile?")
    assert params["detail"] == ["Steam 回调校验失败，请重新发起绑定"]
    assert checked == []

    _location, params = _callback(
        client,
        path,
        state=state,
        **{"openid.mode": "id_res", "openid.return_to": f"{SITE}{path}?state={state}"},
    )
    assert params["detail"] == ["Steam 登录校验未通过"]
    assert len(checked) == 1
