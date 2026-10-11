import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.session_cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    QQ_OAUTH_NONCE_COOKIE,
    SAFE_METHODS,
    attach_session_cookies,
    clear_session_cookies,
    cookie_secure,
    csrf_tokens_match,
    set_qq_oauth_nonce_cookie,
)


def test_csrf_tokens_match_rejects_empty_or_mismatch() -> None:
    assert csrf_tokens_match("abc", "abc") is True
    assert csrf_tokens_match("abc", "abd") is False
    assert csrf_tokens_match("", "abc") is False
    assert csrf_tokens_match("abc", None) is False
    assert csrf_tokens_match("ab", "abc") is False


def test_cookie_and_csrf_header_names() -> None:
    assert ACCESS_COOKIE == "zhange_access"
    assert CSRF_COOKIE == "zhange_csrf"
    assert CSRF_HEADER == "x-csrf-token"
    assert "GET" in SAFE_METHODS
    assert "POST" not in SAFE_METHODS


def _https_request() -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 123),
            "server": ("test", 443),
        }
    )


def test_clear_session_cookies_matches_secure_flag(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    response = Response()
    clear_session_cookies(response, _https_request())
    get_settings.cache_clear()
    headers = [v.decode("latin-1") for k, v in response.raw_headers if k == b"set-cookie"]
    joined = "\n".join(headers).lower()
    assert ACCESS_COOKIE in joined
    assert CSRF_COOKIE in joined
    assert joined.count("secure") >= 2
    assert "samesite=lax" in joined


def _request(scheme: str = "http", headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": scheme,
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(k.encode(), v.encode()) for k, v in (headers or {}).items()],
            "client": ("127.0.0.1", 123),
            "server": ("test", 443 if scheme == "https" else 80),
        }
    )


def _set_cookie_headers(response: Response) -> list[str]:
    return [v.decode("latin-1").lower() for k, v in response.raw_headers if k == b"set-cookie"]


@pytest.mark.parametrize(
    ("env", "scheme", "headers", "setup_response", "expected"),
    [
        ("development", "http", {}, False, False),
        ("development", "http", {"x-forwarded-proto": "https"}, False, True),
        ("development", "https", {}, False, True),
        ("production", "http", {}, False, True),
        ("production", "http", {"x-forwarded-proto": "https, http"}, True, True),
        # 生产首装常是 http 直连：向导建管理员这次不加 Secure，否则装完即掉线
        ("production", "http", {}, True, False),
        ("production", "https", {}, True, True),
    ],
)
def test_cookie_secure_rules(monkeypatch, env, scheme, headers, setup_response, expected) -> None:
    monkeypatch.setenv("APP_ENV", env)
    get_settings.cache_clear()
    req = _request(scheme, headers)
    assert cookie_secure(req, setup_response=setup_response) is expected
    response = Response()
    attach_session_cookies(response, "tok", req, setup_response=setup_response)
    cookies = _set_cookie_headers(response)
    assert len(cookies) == 2
    assert all(("; secure" in c) is expected for c in cookies)
    get_settings.cache_clear()


def test_qq_nonce_cookie_is_scoped_to_callback(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    response = Response()
    set_qq_oauth_nonce_cookie(response, _request("https"), "nonce-value", max_age=900)
    (cookie,) = _set_cookie_headers(response)
    assert cookie.startswith(f"{QQ_OAUTH_NONCE_COOKIE}=nonce-value")
    for attr in ("httponly", "path=/api/auth/qq", "samesite=lax", "secure", "max-age=900"):
        assert attr in cookie
    get_settings.cache_clear()