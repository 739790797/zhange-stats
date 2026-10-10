"""进程内限流器与登录失败退避。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.ephemeral_kv import reset_ephemeral_kv_for_tests
from app.core.rate_limit import (
    LOGIN_FAILURES_BEFORE_LOCK,
    LOGIN_LOCK_MAX_SEC,
    RateLimiter,
    _login_failure_key,
    clear_login_failures,
    ensure_login_not_locked,
    login_lock_seconds,
    record_login_failure,
    reset_rate_limit_redis_for_tests,
)


@pytest.fixture
def memory_backend(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    reset_rate_limit_redis_for_tests()
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()
    get_settings.cache_clear()
    reset_rate_limit_redis_for_tests()


def _fake_clock(monkeypatch, start: float = 1_000_000.0) -> dict:
    clock = {"now": start}
    monkeypatch.setattr(
        "app.core.rate_limit.time",
        SimpleNamespace(monotonic=lambda: clock["now"], time=lambda: clock["now"]),
    )
    return clock


def test_memory_rate_limit_blocks(memory_backend) -> None:
    lim = RateLimiter()
    lim.hit("t:a", limit=2, window_sec=60)
    lim.hit("t:a", limit=2, window_sec=60)
    with pytest.raises(HTTPException) as exc:
        lim.hit("t:a", limit=2, window_sec=60)
    assert exc.value.status_code == 429
    lim.hit("t:b", limit=2, window_sec=60)


def test_rate_limit_switch_off_lets_everything_through(memory_backend, monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    lim = RateLimiter()
    for _ in range(5):
        lim.hit("t:a", limit=1, window_sec=60)


def test_window_slides(memory_backend, monkeypatch) -> None:
    clock = _fake_clock(monkeypatch)
    lim = RateLimiter()
    lim.hit("t:a", limit=1, window_sec=60)
    with pytest.raises(HTTPException):
        lim.hit("t:a", limit=1, window_sec=60)
    clock["now"] += 61
    lim.hit("t:a", limit=1, window_sec=60)


def test_reset_clears_buckets(memory_backend) -> None:
    lim = RateLimiter()
    lim.hit("t:a", limit=1, window_sec=60)
    lim.reset()
    lim.hit("t:a", limit=1, window_sec=60)


def test_sweep_drops_buckets_outside_their_window(memory_backend, monkeypatch) -> None:
    clock = _fake_clock(monkeypatch)
    lim = RateLimiter()
    lim.hit("reset:email:a@example.com", limit=3, window_sec=10)
    lim.hit("reset:email:b@example.com", limit=3, window_sec=600)
    clock["now"] += 120
    lim.hit("other", limit=3, window_sec=10)
    assert "reset:email:a@example.com" not in lim._hits
    assert "reset:email:b@example.com" in lim._hits


def test_login_lock_grows_exponentially_and_caps() -> None:
    free = LOGIN_FAILURES_BEFORE_LOCK
    assert [login_lock_seconds(n) for n in range(free + 1)] == [0] * (free + 1)
    assert login_lock_seconds(free + 1) == 60
    assert login_lock_seconds(free + 2) == 120
    assert login_lock_seconds(free + 3) == 240
    assert login_lock_seconds(free + 50) == LOGIN_LOCK_MAX_SEC


def test_login_failures_lock_account_then_expire(memory_backend, monkeypatch) -> None:
    clock = _fake_clock(monkeypatch)
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK):
        ensure_login_not_locked("Alice@Example.com")
        record_login_failure("Alice@Example.com")
    ensure_login_not_locked("alice@example.com")
    record_login_failure("alice@example.com")
    with pytest.raises(HTTPException) as exc:
        ensure_login_not_locked(" ALICE@example.com ")
    assert exc.value.status_code == 429
    assert "1 分钟" in str(exc.value.detail)
    ensure_login_not_locked("bob@example.com")

    clock["now"] += 61
    ensure_login_not_locked("alice@example.com")
    record_login_failure("alice@example.com")
    with pytest.raises(HTTPException) as exc:
        ensure_login_not_locked("alice@example.com")
    assert "2 分钟" in str(exc.value.detail)


def test_login_success_clears_failures(memory_backend) -> None:
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        record_login_failure("carol")
    with pytest.raises(HTTPException):
        ensure_login_not_locked("carol")
    clear_login_failures("carol")
    ensure_login_not_locked("carol")
    record_login_failure("carol")
    ensure_login_not_locked("carol")


def test_login_backoff_ignores_rate_limit_switch(memory_backend, monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        record_login_failure("dave")
    with pytest.raises(HTTPException):
        ensure_login_not_locked("dave")


def test_login_failure_key_does_not_expose_account() -> None:
    key = _login_failure_key("alice@example.com")
    assert "alice" not in key
    assert key == _login_failure_key(" Alice@Example.COM ")
