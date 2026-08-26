"""Sliding-window rate limiter：默认进程内；配置 REDIS_URL 后跨实例。"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


def _get_redis() -> Any | None:
    from app.core.redis_client import get_redis

    return get_redis()


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_sec: float) -> None:
        r = _get_redis()
        if r is not None:
            self._hit_redis(r, key, limit=limit, window_sec=window_sec)
            return
        self._hit_memory(key, limit=limit, window_sec=window_sec)

    def _hit_memory(self, key: str, *, limit: int, window_sec: float) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window_sec
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="请求过于频繁，请稍后再试",
                )
            bucket.append(now)

    def _hit_redis(
        self,
        r: Any,
        key: str,
        *,
        limit: int,
        window_sec: float,
    ) -> None:
        now = time.time()
        rk = f"zhange:rl:{key}"
        member = f"{now}:{uuid.uuid4().hex}"
        pipe = r.pipeline()
        pipe.zremrangebyscore(rk, 0, now - window_sec)
        pipe.zcard(rk)
        pipe.zadd(rk, {member: now})
        pipe.expire(rk, max(int(window_sec) + 1, 2))
        try:
            _removed, count, *_rest = pipe.execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate_limit: Redis error (%s), fallback memory", exc)
            self._hit_memory(key, limit=limit, window_sec=window_sec)
            return
        # count = size before zadd; reject if already at limit
        if int(count) >= limit:
            try:
                r.zrem(rk, member)
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )


auth_limiter = RateLimiter()
# 平台短信 / 绑定等与 auth 共用限流器
platform_limiter = auth_limiter


def client_ip(request: Request) -> str:
    from app.core.config import get_settings

    if get_settings().TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def reset_rate_limit_redis_for_tests() -> None:
    """测试用：清掉 Redis 探测缓存。"""
    from app.core.redis_client import reset_redis_for_tests

    reset_redis_for_tests()
