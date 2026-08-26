"""共享 Redis 连接。限流与 ephemeral_kv 共用，避免各 from_url 一份。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client: Any | None = None
_checked = False


def get_redis() -> Any | None:
    global _client, _checked
    if _checked:
        return _client
    _checked = True
    try:
        from app.core.config import get_settings

        url = (get_settings().REDIS_URL or "").strip()
    except Exception:  # noqa: BLE001
        return None
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        _client = client
        logger.info("redis_client: connected")
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis_client: unavailable (%s), callers fallback to memory", exc)
        _client = None
    return _client


def reset_redis_for_tests() -> None:
    global _client, _checked
    _client = None
    _checked = False
