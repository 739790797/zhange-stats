"""共享 Redis 连接。限流与 ephemeral_kv 共用，避免各 from_url 一份。"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from app.core.biz_logging import clear_log_until_change, log_until_change

logger = logging.getLogger(__name__)

RETRY_AFTER_SEC = 30.0
# 连接失败后其余线程最多等这么久就回退内存，不跟着卡在超时上。
_CONNECT_WAIT_SEC = 0.5
_CLIENT_KWARGS: dict[str, Any] = {
    "decode_responses": True,
    "socket_connect_timeout": 2,
    "socket_timeout": 2,
    "health_check_interval": 30,
    "retry_on_timeout": True,
}
_LOG_KEY = "redis_client.connect"
_CRED_IN_URL = re.compile(r"((?:redis|rediss|unix)://)([^@\s/]+)@", re.I)

_lock = threading.Lock()
_client: Any | None = None
_url = ""
_retry_at = 0.0
_monotonic = time.monotonic


def _configured_url() -> str:
    try:
        from app.core.config import get_settings

        return (get_settings().REDIS_URL or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _redact(exc: BaseException) -> str:
    text = _CRED_IN_URL.sub(r"\1***@", str(exc).replace("\n", " ").strip())
    return text[:240] or exc.__class__.__name__


def _close_quietly(client: Any) -> None:
    try:
        client.close()
    except Exception:  # noqa: BLE001
        pass


def _connect_locked(url: str) -> Any | None:
    global _client, _url, _retry_at
    old, _client, _url = _client, None, url
    if old is not None:
        _close_quietly(old)
    client: Any | None = None
    try:
        import redis

        client = redis.Redis.from_url(url, **_CLIENT_KWARGS)
        client.ping()
    except Exception as exc:  # noqa: BLE001
        if client is not None:
            _close_quietly(client)
        _retry_at = _monotonic() + RETRY_AFTER_SEC
        log_until_change(
            logger,
            _LOG_KEY,
            "redis_client: unavailable (%s), callers fallback to memory; retry every %.0fs",
            _redact(exc),
            RETRY_AFTER_SEC,
        )
        return None
    _client = client
    _retry_at = 0.0
    clear_log_until_change(_LOG_KEY)
    logger.info("redis_client: connected")
    return client


def get_redis() -> Any | None:
    """已连通的共享客户端；未配置或不可用时 None（调用方回退内存），失败后隔 RETRY_AFTER_SEC 再连。"""
    url = _configured_url()
    if not url:
        return None
    client = _client
    if client is not None and _url == url:
        return client
    if _url == url and _monotonic() < _retry_at:
        return None
    if not _lock.acquire(timeout=_CONNECT_WAIT_SEC):
        return None
    try:
        if _url == url:
            if _client is not None:
                return _client
            if _monotonic() < _retry_at:
                return None
        return _connect_locked(url)
    finally:
        _lock.release()


def reset_redis_for_tests() -> None:
    global _client, _url, _retry_at
    with _lock:
        _client = None
        _url = ""
        _retry_at = 0.0
    clear_log_until_change(_LOG_KEY)
