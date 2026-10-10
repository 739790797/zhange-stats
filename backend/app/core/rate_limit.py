"""Sliding-window rate limiter：默认进程内；配置 REDIS_URL 后跨实例。"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException, Request, status

from app.core.biz_logging import clear_log_until_change, log_until_change

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_SEC = 60.0
# 同一账号 + 同一 IP 前几次输错不锁；之后每错一次锁定时长翻倍（1、2、4、8 分钟…封顶 15 分钟）。
# 按 (账号, IP) 锁，别人从别处乱输锁不住本人
LOGIN_FAILURES_BEFORE_LOCK = 4
LOGIN_LOCK_BASE_SEC = 60
LOGIN_LOCK_MAX_SEC = 15 * 60
# 最后一次输错后这么久没再错，失败计数归零
LOGIN_FAILURE_MEMORY_SEC = 60 * 60
# 账号维度只设高得多的上限（换 IP 撞库）：累计这么多次后整号锁一小会，计数重来
LOGIN_ACCOUNT_FAILURES_BEFORE_LOCK = 50
LOGIN_ACCOUNT_LOCK_SEC = 5 * 60


def _get_redis() -> Any | None:
    from app.core.redis_client import get_redis

    return get_redis()


def rate_limit_enabled() -> bool:
    from app.core.config import get_settings

    return bool(get_settings().RATE_LIMIT_ENABLED)


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._windows: dict[str, float] = {}
        self._last_sweep = time.monotonic()

    def hit(self, key: str, *, limit: int, window_sec: float) -> None:
        if not rate_limit_enabled():
            return
        r = _get_redis()
        if r is not None:
            self._hit_redis(r, key, limit=limit, window_sec=window_sec)
            return
        self._hit_memory(key, limit=limit, window_sec=window_sec)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._windows.clear()

    def _sweep_locked(self, now: float) -> None:
        # 按邮箱 / 账号分桶时键不可枚举，定期丢掉窗口外的桶，免得进程内存只涨不落
        if now - self._last_sweep < _SWEEP_INTERVAL_SEC:
            return
        self._last_sweep = now
        dead = [
            k
            for k, bucket in self._hits.items()
            if not bucket or bucket[-1] <= now - self._windows.get(k, 0.0)
        ]
        for k in dead:
            self._hits.pop(k, None)
            self._windows.pop(k, None)

    def _hit_memory(self, key: str, *, limit: int, window_sec: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._sweep_locked(now)
            bucket = self._hits[key]
            self._windows[key] = max(float(window_sec), self._windows.get(key, 0.0))
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
            log_until_change(
                logger, "rate_limit.redis", "rate_limit: Redis error (%s), fallback memory", exc
            )
            self._hit_memory(key, limit=limit, window_sec=window_sec)
            return
        clear_log_until_change("rate_limit.redis")
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


def _forwarded_for_values(request: Request) -> list[str]:
    headers = request.headers
    getlist = getattr(headers, "getlist", None)
    raw = getlist("x-forwarded-for") if callable(getlist) else [headers.get("x-forwarded-for")]
    return [part.strip() for line in raw if line for part in str(line).split(",")]


def client_ip(request: Request) -> str:
    from app.core.config import get_settings

    if get_settings().TRUST_X_FORWARDED_FOR:
        # 受信反代把它看到的对端追加在最右；左侧各段由客户端自填，可伪造
        values = _forwarded_for_values(request)
        if values and values[-1]:
            return values[-1]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _login_digest(*parts: str) -> str:
    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _login_ident(account: str) -> str:
    return (account or "").strip().lower()


def _login_failure_key(account: str, ip: str) -> str:
    return f"zhange:login-fail:{_login_digest(_login_ident(account), ip or 'unknown')}"


def _login_lock_key(account: str, ip: str) -> str:
    return f"zhange:login-lock:{_login_digest(_login_ident(account), ip or 'unknown')}"


def _account_failure_key(account: str) -> str:
    return f"zhange:login-fail-account:{_login_digest(_login_ident(account))}"


def _account_lock_key(account: str) -> str:
    return f"zhange:login-lock-account:{_login_digest(_login_ident(account))}"


def login_lock_seconds(failures: int) -> int:
    over = int(failures) - LOGIN_FAILURES_BEFORE_LOCK
    if over <= 0:
        return 0
    return min(LOGIN_LOCK_MAX_SEC, LOGIN_LOCK_BASE_SEC * 2 ** min(over - 1, 16))


def _lock_remaining(key: str) -> float:
    from app.core.ephemeral_kv import ephemeral_get

    try:
        locked_until = float(ephemeral_get(key) or 0)
    except ValueError:
        return 0.0
    return locked_until - time.time()


def _set_lock(key: str, seconds: int) -> None:
    from app.core.ephemeral_kv import ephemeral_set

    ephemeral_set(key, f"{time.time() + seconds:.0f}", ttl_sec=seconds + 1)


def ensure_login_not_locked(account: str, ip: str) -> None:
    """锁定期内直接拒绝，不再校验口令（也省掉一次 bcrypt）。

    键用用户输入的账号名，不管账号是否存在，免得锁与不锁泄露账号存在性。
    """
    remaining = max(
        _lock_remaining(_login_lock_key(account, ip)),
        _lock_remaining(_account_lock_key(account)),
    )
    if remaining > 0:
        minutes = max(1, math.ceil(remaining / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {minutes} 分钟后再试",
        )


def record_login_failure(account: str, ip: str) -> None:
    from app.core.ephemeral_kv import ephemeral_delete, ephemeral_incr

    failures = ephemeral_incr(
        _login_failure_key(account, ip), ttl_sec=LOGIN_FAILURE_MEMORY_SEC
    )
    lock = login_lock_seconds(failures)
    if lock:
        _set_lock(_login_lock_key(account, ip), lock)
    account_failures = ephemeral_incr(
        _account_failure_key(account), ttl_sec=LOGIN_FAILURE_MEMORY_SEC
    )
    if account_failures >= LOGIN_ACCOUNT_FAILURES_BEFORE_LOCK:
        _set_lock(_account_lock_key(account), LOGIN_ACCOUNT_LOCK_SEC)
        ephemeral_delete(_account_failure_key(account))


def clear_login_failures(account: str, ip: str, *, account_wide: bool = False) -> None:
    """登录成功只清本 IP 的计数；账号维度计数只在证明了邮箱归属（重置密码）后才清。"""
    from app.core.ephemeral_kv import ephemeral_delete

    ephemeral_delete(_login_failure_key(account, ip))
    ephemeral_delete(_login_lock_key(account, ip))
    if account_wide:
        ephemeral_delete(_account_failure_key(account))
        ephemeral_delete(_account_lock_key(account))


def reset_rate_limit_redis_for_tests() -> None:
    """测试用：清掉 Redis 探测缓存。"""
    from app.core.redis_client import reset_redis_for_tests

    reset_redis_for_tests()


def reset_rate_limits_for_tests() -> None:
    """测试用：清空进程内限流桶（登录失败计数在 ephemeral_kv，另见 reset_ephemeral_kv_for_tests）。"""
    auth_limiter.reset()
