"""进程内限流器与登录失败退避。"""

import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.ephemeral_kv import ephemeral_get, reset_ephemeral_kv_for_tests
from app.core.rate_limit import (
    LOGIN_ACCOUNT_FAILURES_BEFORE_LOCK,
    LOGIN_ACCOUNT_LOCK_SEC,
    LOGIN_FAILURES_BEFORE_LOCK,
    LOGIN_LOCK_MAX_SEC,
    RateLimiter,
    _account_failure_key,
    _login_failure_key,
    _login_lock_key,
    clear_login_failures,
    ensure_login_not_locked,
    login_lock_seconds,
    record_login_failure,
    reset_rate_limit_redis_for_tests,
)

IP = "203.0.113.7"
OTHER_IP = "198.51.100.9"


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


def test_login_failures_lock_account_and_ip_then_expire(memory_backend, monkeypatch) -> None:
    clock = _fake_clock(monkeypatch)
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK):
        ensure_login_not_locked("Alice@Example.com", IP)
        record_login_failure("Alice@Example.com", IP)
    ensure_login_not_locked("alice@example.com", IP)
    record_login_failure("alice@example.com", IP)
    with pytest.raises(HTTPException) as exc:
        ensure_login_not_locked(" ALICE@example.com ", IP)
    assert exc.value.status_code == 429
    assert "1 分钟" in str(exc.value.detail)
    ensure_login_not_locked("bob@example.com", IP)

    clock["now"] += 61
    ensure_login_not_locked("alice@example.com", IP)
    record_login_failure("alice@example.com", IP)
    with pytest.raises(HTTPException) as exc:
        ensure_login_not_locked("alice@example.com", IP)
    assert "2 分钟" in str(exc.value.detail)


def test_lock_from_one_ip_does_not_lock_the_owner_elsewhere(memory_backend) -> None:
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 3):
        record_login_failure("admin", IP)
    with pytest.raises(HTTPException):
        ensure_login_not_locked("admin", IP)
    ensure_login_not_locked("admin", OTHER_IP)


def test_account_ceiling_locks_every_ip_then_restarts(memory_backend, monkeypatch) -> None:
    clock = _fake_clock(monkeypatch)
    # 每个 IP 都停在免锁次数内：只有账号维度的上限能拦住换 IP 撞库
    for n in range(LOGIN_ACCOUNT_FAILURES_BEFORE_LOCK):
        ip = f"10.0.{n // LOGIN_FAILURES_BEFORE_LOCK}.1"
        ensure_login_not_locked("admin", ip)
        record_login_failure("admin", ip)
    with pytest.raises(HTTPException) as exc:
        ensure_login_not_locked("admin", "192.0.2.200")
    assert exc.value.status_code == 429
    assert f"{LOGIN_ACCOUNT_LOCK_SEC // 60} 分钟" in str(exc.value.detail)
    ensure_login_not_locked("someone-else", "192.0.2.200")

    clock["now"] += LOGIN_ACCOUNT_LOCK_SEC + 1
    ensure_login_not_locked("admin", "192.0.2.200")
    record_login_failure("admin", "192.0.2.200")
    ensure_login_not_locked("admin", "192.0.2.201")


def test_login_success_clears_only_this_ip(memory_backend) -> None:
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        record_login_failure("carol", IP)
    record_login_failure("carol", OTHER_IP)
    with pytest.raises(HTTPException):
        ensure_login_not_locked("carol", IP)
    clear_login_failures("carol", IP)
    ensure_login_not_locked("carol", IP)
    record_login_failure("carol", IP)
    ensure_login_not_locked("carol", IP)
    assert ephemeral_get(_login_failure_key("carol", OTHER_IP)) == "1"
    assert ephemeral_get(_account_failure_key("carol")) == str(LOGIN_FAILURES_BEFORE_LOCK + 3)


def test_account_wide_clear_lifts_the_account_lock(memory_backend) -> None:
    for n in range(LOGIN_ACCOUNT_FAILURES_BEFORE_LOCK):
        record_login_failure("erin", f"10.1.{n}.1")
    with pytest.raises(HTTPException):
        ensure_login_not_locked("erin", IP)
    clear_login_failures("erin", IP)
    with pytest.raises(HTTPException):
        ensure_login_not_locked("erin", IP)
    clear_login_failures("erin", IP, account_wide=True)
    ensure_login_not_locked("erin", IP)


def test_login_backoff_ignores_rate_limit_switch(memory_backend, monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    for _ in range(LOGIN_FAILURES_BEFORE_LOCK + 1):
        record_login_failure("dave", IP)
    with pytest.raises(HTTPException):
        ensure_login_not_locked("dave", IP)


def test_concurrent_failures_are_all_counted(memory_backend) -> None:
    threads = 6
    per_thread = 5
    barrier = threading.Barrier(threads)

    def worker() -> None:
        barrier.wait()
        for _ in range(per_thread):
            record_login_failure("frank", IP)

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert ephemeral_get(_login_failure_key("frank", IP)) == str(threads * per_thread)


def test_login_failure_keys_do_not_expose_account_or_ip() -> None:
    key = _login_failure_key("alice@example.com", IP)
    assert "alice" not in key and IP not in key
    assert key == _login_failure_key(" Alice@Example.COM ", IP)
    assert key != _login_failure_key("alice@example.com", OTHER_IP)
    assert _login_lock_key("alice@example.com", IP) != key
    account_key = _account_failure_key("alice@example.com")
    assert "alice" not in account_key
    assert account_key == _account_failure_key("ALICE@example.com ")
