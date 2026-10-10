import logging

import anyio
import pytest

from app.core.request_log_middleware import RequestLogMiddleware, should_log_request


def _http_scope(method: str, path: str) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "client": ("10.0.0.5", 1234),
    }


async def _noop_receive() -> dict:
    return {"type": "http.request", "body": b"", "more_body": False}


def test_skips_health_and_assets() -> None:
    assert should_log_request("GET", "/health", 200, 5) is False
    assert should_log_request("GET", "/assets/app.js", 200, 5) is False
    assert should_log_request("GET", "/api/settings/runtime-health", 200, 5) is False
    assert should_log_request("POST", "/api/client-rum", 200, 8) is False
    assert should_log_request("POST", "/api/client-rum", 500, 8) is False


def test_logs_writes_errors_and_slow_gets() -> None:
    assert should_log_request("POST", "/api/auth/login", 200, 10) is True
    assert should_log_request("GET", "/api/steam/overview", 500, 10) is True
    assert should_log_request("GET", "/api/steam/overview", 200, 250) is True
    assert should_log_request("GET", "/api/steam/overview", 200, 20) is False


def test_app_exception_propagates_and_is_logged_as_500(caplog) -> None:
    async def boom(scope, receive, send):
        raise RuntimeError("kaput")

    mw = RequestLogMiddleware(boom)

    async def send(message):
        raise AssertionError("no response expected")

    with caplog.at_level(logging.INFO, logger="zhange.http"):
        with pytest.raises(RuntimeError, match="kaput"):
            anyio.run(mw, _http_scope("POST", "/api/demo"), _noop_receive, send)
    msgs = [r.getMessage() for r in caplog.records if r.name == "zhange.http"]
    assert any(m.startswith("POST /api/demo -> 500") for m in msgs)


def test_skipped_request_exception_still_propagates(caplog) -> None:
    async def boom(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise ValueError("late failure")

    mw = RequestLogMiddleware(boom)
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    with caplog.at_level(logging.INFO, logger="zhange.http"):
        with pytest.raises(ValueError):
            anyio.run(mw, _http_scope("GET", "/api/fast"), _noop_receive, send)
    assert sent[0]["status"] == 200
    assert not [r for r in caplog.records if r.name == "zhange.http"]
