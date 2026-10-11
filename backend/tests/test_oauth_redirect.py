"""OAuth 回跳只去白名单前端；QQ / Steam state 绑定发起授权的浏览器（nonce Cookie）；回跳只带固定 reason 码。"""

from __future__ import annotations

import secrets
import urllib.parse
from types import SimpleNamespace

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
from app.core.session_cookies import QQ_OAUTH_NONCE_COOKIE, STEAM_OPENID_NONCE_COOKIE
from app.core.timeutil import utc_now
from app.models.member import Member
from app.models.user import User, UserRole
from app.services.email import NOTICE_QQ_LINKED
from app.services.qq_oauth import (
    PURPOSE_BIND,
    PURPOSE_LOGIN,
    QqOAuthError,
    QqProfile,
    create_qq_oauth_state,
    decode_qq_oauth_state,
    new_oauth_nonce,
)
from app.services.steam import openid as steam_openid

SITE = "https://site.example"
EVIL = "https://evil.example"
STEAM_CALLBACK = "/api/profile/steam/openid/callback"
SID = "76561198000000000"


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
    assert params == {"qq_login": ["error"], "reason": ["browser_mismatch"]}
    with SessionLocal() as db:
        assert db.query(User).count() == 0


def test_callback_in_same_browser_issues_ticket_once(oauth_app) -> None:
    api, SessionLocal = oauth_app
    client = TestClient(api, base_url=SITE)
    state = _state_from_start(client.get("/api/auth/qq/oauth/start"))
    location, params = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert location.startswith(f"{SITE}/login?")
    assert set(params) == {"qq_login", "ticket", "need_complete"}
    assert params["qq_login"] == ["ok"]
    assert params["ticket"][0]
    assert "小明" not in urllib.parse.unquote(location)
    assert client.cookies.get(QQ_OAUTH_NONCE_COOKIE) is None

    _again, replay = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert replay == {"qq_login": ["error"], "reason": ["browser_mismatch"]}
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


@pytest.mark.parametrize(
    "error,reason",
    [("access_denied", "cancelled"), ("server_error", "upstream_error")],
)
def test_qq_error_param_maps_to_reason_code(oauth_app, error, reason) -> None:
    api, _ = oauth_app
    client = TestClient(api, base_url=SITE)
    state = _state_from_start(client.get("/api/auth/qq/oauth/start"))
    location, params = _callback(
        client,
        "/api/auth/qq/callback",
        state=state,
        error=error,
        error_description="<script>alert(1)</script>请联系客服",
    )
    assert params == {"qq_login": ["error"], "reason": [reason]}
    assert "script" not in location and "客服" not in urllib.parse.unquote(location)


def test_qq_error_param_cannot_forge_log_lines(oauth_app, caplog) -> None:
    api, _ = oauth_app
    client = TestClient(api, base_url=SITE)
    state = _state_from_start(client.get("/api/auth/qq/oauth/start"))
    with caplog.at_level("INFO", logger="app.api.profile.qq"):
        _loc, params = _callback(
            client,
            "/api/auth/qq/callback",
            state=state,
            error="x\nINFO admin logged in",
        )
    assert params == {"qq_login": ["error"], "reason": ["upstream_error"]}
    messages = [r.getMessage() for r in caplog.records if r.name == "app.api.profile.qq"]
    assert any("reason=upstream_error" in m for m in messages)
    assert all("\n" not in m for m in messages)


def test_qq_invalid_state_and_missing_code(oauth_app) -> None:
    api, _ = oauth_app
    client = TestClient(api, base_url=SITE)
    _loc, params = _callback(client, "/api/auth/qq/callback", code="c", state="not-a-jwt")
    assert params == {"qq_login": ["error"], "reason": ["state_invalid"]}
    state = _state_from_start(client.get("/api/auth/qq/oauth/start"))
    _loc, params = _callback(client, "/api/auth/qq/callback", state=state)
    assert params == {"qq_login": ["error"], "reason": ["missing_code"]}


@pytest.mark.parametrize(
    "exc,reason",
    [
        (QqOAuthError("QQ 返回：access token 12345 invalid"), "upstream_error"),
        (RuntimeError("(pymysql.err) SELECT password_hash FROM users"), "server_error"),
    ],
)
def test_qq_login_failures_never_put_exception_text_in_url(oauth_app, monkeypatch, exc, reason) -> None:
    api, SessionLocal = oauth_app

    def _boom(_code, backend=None):
        raise exc

    monkeypatch.setattr("app.api.profile.qq.exchange_code_for_profile", _boom)
    client = TestClient(api, base_url=SITE)
    state = _state_from_start(client.get("/api/auth/qq/oauth/start"))
    location, params = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert params == {"qq_login": ["error"], "reason": [reason]}
    assert "SELECT" not in location and "12345" not in location
    with SessionLocal() as db:
        assert db.query(User).count() == 0


def _start_qq_bind(client: TestClient, token: str) -> str:
    return _state_from_start(
        client.get("/api/profile/qq/oauth/start", headers={"authorization": f"Bearer {token}"})
    )


def test_qq_bind_conflict_maps_to_already_bound(oauth_app) -> None:
    api, SessionLocal = oauth_app
    _uid, mid, token = _bind_target(SessionLocal)
    with SessionLocal() as db:
        db.add(Member(nickname="bob", qq_openid="openid-victim"))
        db.commit()
    client = TestClient(api, base_url=SITE)
    state = _start_qq_bind(client, token)
    location, params = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert location.startswith(f"{SITE}/profile?")
    assert params == {"qq_bind": ["error"], "reason": ["already_bound"]}
    with SessionLocal() as db:
        assert db.get(Member, mid).qq_openid is None


def test_qq_bind_success_notifies_the_account_owner(oauth_app, monkeypatch) -> None:
    api, SessionLocal = oauth_app
    notified: list[tuple] = []
    monkeypatch.setattr("app.api.profile.qq.notify_account_event", lambda *a: notified.append(a))
    _uid, _mid, token = _bind_target(SessionLocal)
    client = TestClient(api, base_url=SITE)
    state = _start_qq_bind(client, token)
    _loc, params = _callback(client, "/api/auth/qq/callback", code="c", state=state)
    assert params == {"qq_bind": ["ok"]}
    assert notified == [("alice@example.com", NOTICE_QQ_LINKED)]


@pytest.fixture
def steam_ready(monkeypatch):
    """Steam 功能开着、有 Key、Steam 资料可查；check_authentication 由 responses 决定。"""
    monkeypatch.setattr("app.services.platform_features.is_feature_enabled", lambda _db, _fid: True)
    monkeypatch.setattr("app.services.integrations_config.get_steam_api_key", lambda _db=None: "k")
    monkeypatch.setattr(
        "app.services.steam.bind.lookup_steam_profile",
        lambda value: SimpleNamespace(
            steam_id=value, is_public=True, persona_name="Gabe", avatar_url=None
        ),
    )
    checks: list[str] = []

    def _steam(method: str, url: str, **_kw):
        checks.append(method)
        return SimpleNamespace(status_code=200, text="ns:http://specs.openid.net/auth/2.0\nis_valid:true\n")

    monkeypatch.setattr(steam_openid, "http_request", _steam)
    return checks


def _steam_start(client: TestClient, token: str):
    resp = client.get(
        "/api/profile/steam/openid/start",
        headers={"origin": EVIL, "authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    login = urllib.parse.parse_qs(urllib.parse.urlparse(resp.json()["url"]).query)
    return_to = login["openid.return_to"][0]
    state = urllib.parse.parse_qs(urllib.parse.urlparse(return_to).query)["state"][0]
    return resp, return_to, state


def _steam_assertion(return_to: str, **overrides: str) -> dict[str, str]:
    claimed = f"https://steamcommunity.com/openid/id/{SID}"
    query = {
        "openid.ns": steam_openid.OPENID_NS,
        "openid.mode": "id_res",
        "openid.op_endpoint": steam_openid.STEAM_OPENID_ENDPOINT,
        "openid.claimed_id": claimed,
        "openid.identity": claimed,
        "openid.return_to": return_to,
        "openid.response_nonce": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ") + secrets.token_hex(4),
        "openid.assoc_handle": "1234567890",
        "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
        "openid.sig": "c2ln",
    }
    query.update(overrides)
    return query


def test_steam_start_binds_state_to_this_browser(oauth_app, steam_ready) -> None:
    api, SessionLocal = oauth_app
    _uid, _mid, token = _bind_target(SessionLocal)
    resp, return_to, state = _steam_start(TestClient(api, base_url=SITE), token)
    assert return_to == f"{SITE}{STEAM_CALLBACK}?state={state}"
    data = steam_openid.decode_openid_state(state)
    assert data["frontend"] == SITE
    cookie = resp.headers["set-cookie"].lower()
    assert cookie.startswith(STEAM_OPENID_NONCE_COOKIE)
    for attr in ("httponly", "path=/api/profile/steam/openid", "secure", "samesite=lax"):
        assert attr in cookie


def test_steam_callback_binds_once_in_the_starting_browser(oauth_app, steam_ready) -> None:
    api, SessionLocal = oauth_app
    _uid, mid, token = _bind_target(SessionLocal)
    client = TestClient(api, base_url=SITE)
    _resp, return_to, state = _steam_start(client, token)
    query = _steam_assertion(return_to)
    location, params = _callback(client, STEAM_CALLBACK, state=state, **query)
    assert location.startswith(f"{SITE}/profile?")
    assert params == {"steam_bind": ["ok"]}
    assert steam_ready == ["POST"]
    assert client.cookies.get(STEAM_OPENID_NONCE_COOKIE) is None
    with SessionLocal() as db:
        assert db.get(Member, mid).steam_id == SID

    _loc, params = _callback(client, STEAM_CALLBACK, state=state, **query)
    assert params == {"steam_bind": ["error"], "reason": ["browser_mismatch"]}
    assert steam_ready == ["POST"]


def test_steam_state_is_single_use_even_with_a_fresh_assertion(oauth_app, steam_ready) -> None:
    api, SessionLocal = oauth_app
    _uid, _mid, token = _bind_target(SessionLocal)
    client = TestClient(api, base_url=SITE)
    resp, return_to, state = _steam_start(client, token)
    nonce_cookie = client.cookies.get(STEAM_OPENID_NONCE_COOKIE)
    assert _callback(client, STEAM_CALLBACK, state=state, **_steam_assertion(return_to))[1] == {
        "steam_bind": ["ok"]
    }
    client.cookies.set(
        STEAM_OPENID_NONCE_COOKIE, nonce_cookie, domain="site.example", path="/api/profile/steam/openid"
    )
    _loc, params = _callback(client, STEAM_CALLBACK, state=state, **_steam_assertion(return_to))
    assert params == {"steam_bind": ["error"], "reason": ["state_invalid"]}
    assert steam_ready == ["POST"]


def test_steam_callback_from_another_browser_is_refused(oauth_app, steam_ready) -> None:
    api, SessionLocal = oauth_app
    _uid, mid, token = _bind_target(SessionLocal)
    _resp, return_to, state = _steam_start(TestClient(api, base_url=SITE), token)
    victim = TestClient(api, base_url=SITE)
    _loc, params = _callback(victim, STEAM_CALLBACK, state=state, **_steam_assertion(return_to))
    assert params == {"steam_bind": ["error"], "reason": ["browser_mismatch"]}
    assert steam_ready == []
    with SessionLocal() as db:
        assert db.get(Member, mid).steam_id is None


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"openid.return_to": "https://other-site.example/steam/return?state=x"}, "verify_failed"),
        ({"openid.signed": "op_endpoint,claimed_id,identity,assoc_handle"}, "verify_failed"),
        ({"openid.response_nonce": "2001-01-01T00:00:00Zabc"}, "expired"),
        ({"openid.mode": "cancel"}, "cancelled"),
    ],
)
def test_steam_bad_assertions_map_to_reason_codes(oauth_app, steam_ready, overrides, reason) -> None:
    api, SessionLocal = oauth_app
    _uid, mid, token = _bind_target(SessionLocal)
    client = TestClient(api, base_url=SITE)
    _resp, return_to, state = _steam_start(client, token)
    location, params = _callback(
        client, STEAM_CALLBACK, state=state, **_steam_assertion(return_to, **overrides)
    )
    assert location.startswith(f"{SITE}/profile?")
    assert params == {"steam_bind": ["error"], "reason": [reason]}
    assert steam_ready == []
    with SessionLocal() as db:
        assert db.get(Member, mid).steam_id is None


def test_steam_invalid_state_is_refused(oauth_app, steam_ready) -> None:
    api, _ = oauth_app
    client = TestClient(api, base_url=SITE)
    location, params = _callback(client, STEAM_CALLBACK, state="forged.state.value")
    assert location.startswith(f"{SITE}/profile?")
    assert params == {"steam_bind": ["error"], "reason": ["state_invalid"]}


def test_steam_already_bound_and_server_errors_use_fixed_codes(oauth_app, steam_ready, monkeypatch) -> None:
    api, SessionLocal = oauth_app
    _uid, _mid, token = _bind_target(SessionLocal)
    with SessionLocal() as db:
        db.add(Member(nickname="bob", steam_id=SID))
        db.commit()
    client = TestClient(api, base_url=SITE)
    _resp, return_to, state = _steam_start(client, token)
    _loc, params = _callback(client, STEAM_CALLBACK, state=state, **_steam_assertion(return_to))
    assert params == {"steam_bind": ["error"], "reason": ["already_bound"]}

    def _db_down(*_a, **_kw):
        raise RuntimeError("(pymysql.err.OperationalError) SELECT secret FROM members")

    monkeypatch.setattr("app.api.profile.steam._set_steam_id", _db_down)
    _resp, return_to, state = _steam_start(client, token)
    location, params = _callback(client, STEAM_CALLBACK, state=state, **_steam_assertion(return_to))
    assert params == {"steam_bind": ["error"], "reason": ["server_error"]}
    assert "SELECT" not in location
