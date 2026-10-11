"""WebSocket Origin 白名单：同源 / PUBLIC_* / CORS 放行，跨站拒绝。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.ws_origin import origin_allowed, websocket_origin_allowed


class _FakeWs:
    def __init__(self, headers: dict[str, str], path: str = "/api/guides/tarkov/raid-rooms/x/ws"):
        self.headers = headers
        self.url = SimpleNamespace(path=path)


@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "")
    monkeypatch.setenv("CORS_ORIGIN_REGEX", "")
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "")
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_same_host_allowed(prod_env) -> None:
    ws = _FakeWs({"origin": "https://stats.example.org", "host": "stats.example.org"})
    assert websocket_origin_allowed(ws) is True


def test_cross_site_rejected(prod_env) -> None:
    ws = _FakeWs({"origin": "https://evil.example", "host": "stats.example.org"})
    assert websocket_origin_allowed(ws) is False


def test_sibling_subdomain_rejected(prod_env) -> None:
    ws = _FakeWs({"origin": "https://blog.example.org", "host": "stats.example.org"})
    assert websocket_origin_allowed(ws) is False


def test_null_origin_rejected(prod_env) -> None:
    ws = _FakeWs({"origin": "null", "host": "stats.example.org"})
    assert websocket_origin_allowed(ws) is False


def test_missing_origin_allowed_for_non_browser_clients(prod_env) -> None:
    ws = _FakeWs({"host": "stats.example.org"})
    assert websocket_origin_allowed(ws) is True


def test_public_frontend_url_allowed_when_proxy_rewrites_host(prod_env, monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_FRONTEND_URL", "https://stats.example.org/")
    get_settings.cache_clear()
    ws = _FakeWs({"origin": "https://stats.example.org", "host": "127.0.0.1:8000"})
    assert websocket_origin_allowed(ws) is True


def test_cors_origins_allowed(prod_env, monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.org, https://other.example.org")
    get_settings.cache_clear()
    assert origin_allowed("https://other.example.org", request_hosts={"127.0.0.1:8000"}) is True
    assert origin_allowed("https://nope.example.org", request_hosts={"127.0.0.1:8000"}) is False


def test_dev_vite_origin_allowed_by_default_regex(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("CORS_ORIGIN_REGEX", "")
    get_settings.cache_clear()
    try:
        assert origin_allowed("http://127.0.0.1:6131", request_hosts={"127.0.0.1:6130"}) is True
        assert origin_allowed("https://evil.example", request_hosts={"127.0.0.1:6130"}) is False
    finally:
        get_settings.cache_clear()
