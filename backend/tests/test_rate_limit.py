"""进程内限流器。"""

from app.core.rate_limit import RateLimiter, reset_rate_limit_redis_for_tests


def test_memory_rate_limit_blocks(monkeypatch) -> None:
    reset_rate_limit_redis_for_tests()
    monkeypatch.setenv("REDIS_URL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_rate_limit_redis_for_tests()

    lim = RateLimiter()
    lim.hit("t:a", limit=2, window_sec=60)
    lim.hit("t:a", limit=2, window_sec=60)
    lim.hit("t:a", limit=2, window_sec=60)
    get_settings.cache_clear()
