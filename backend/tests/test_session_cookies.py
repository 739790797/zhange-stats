from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.session_cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    SAFE_METHODS,
    clear_session_cookies,
    csrf_tokens_match,
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