from app.core.request_log_middleware import should_log_request


def test_skips_health_and_assets() -> None:
    assert should_log_request("GET", "/health", 200, 5) is False
    assert should_log_request("GET", "/assets/app.js", 200, 5) is False
    assert should_log_request("GET", "/api/settings/runtime-health", 200, 5) is False


def test_logs_writes_errors_and_slow_gets() -> None:
    assert should_log_request("POST", "/api/auth/login", 200, 10) is True
    assert should_log_request("GET", "/api/steam/overview", 500, 10) is True
    assert should_log_request("GET", "/api/steam/overview", 200, 250) is True
    assert should_log_request("GET", "/api/steam/overview", 200, 20) is False
