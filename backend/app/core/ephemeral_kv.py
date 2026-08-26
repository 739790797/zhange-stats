"""短时 KV：默认进程内；配置 REDIS_URL 后跨实例（扫码会话 / cred 缓存等）。

多 app 副本必须共享同一 REDIS_URL，否则 pending / cred 不互通。
当前产品按单副本设计；见 README「部署形态」。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_memory: dict[str, tuple[str, float]] = {}


def _get_redis() -> Any | None:
    from app.core.redis_client import get_redis

    return get_redis()


def ephemeral_set(key: str, value: str, *, ttl_sec: int) -> None:
    """写入字符串值；ttl_sec 必须 > 0。"""
    if ttl_sec <= 0:
        raise ValueError("ttl_sec must be positive")
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, int(ttl_sec), value)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("ephemeral_kv set Redis failed (%s), fallback memory", exc)
    expires = time.time() + float(ttl_sec)
    with _lock:
        _purge_memory_locked(time.time())
        _memory[key] = (value, expires)


def ephemeral_get(key: str) -> str | None:
    r = _get_redis()
    if r is not None:
        try:
            val = r.get(key)
            if val is not None:
                return str(val)
            # Redis miss：不回退读内存，避免双写不一致
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("ephemeral_kv get Redis failed (%s), fallback memory", exc)
    now = time.time()
    with _lock:
        _purge_memory_locked(now)
        row = _memory.get(key)
        if row is None:
            return None
        value, expires = row
        if expires <= now:
            _memory.pop(key, None)
            return None
        return value


def ephemeral_delete(key: str) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ephemeral_kv delete Redis failed (%s)", exc)
    with _lock:
        _memory.pop(key, None)


def _purge_memory_locked(now: float) -> None:
    dead = [k for k, (_, exp) in _memory.items() if exp <= now]
    for k in dead:
        _memory.pop(k, None)


def reset_ephemeral_kv_for_tests() -> None:
    """测试用：清空内存态并重置 Redis 探测。"""
    from app.core.redis_client import reset_redis_for_tests

    reset_redis_for_tests()
    with _lock:
        _memory.clear()
