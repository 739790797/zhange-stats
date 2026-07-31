"""In-memory sliding-window rate limiter for auth endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_sec: float) -> None:
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


auth_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
