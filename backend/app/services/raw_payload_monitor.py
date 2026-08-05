"""监控落库的 raw / payload JSON 体积。"""

from __future__ import annotations

import logging

logger = logging.getLogger("zhange.raw_payload")

WARN_BYTES = 512 * 1024
CRITICAL_BYTES = 2 * 1024 * 1024


def note_raw_payload(kind: str, payload: str | bytes, **ctx: object) -> int:
    """记录体积；超阈值打日志。返回字节数。"""
    if isinstance(payload, bytes):
        size = len(payload)
    else:
        size = len(payload.encode("utf-8"))
    extra = " ".join(f"{k}={v}" for k, v in ctx.items() if v is not None)
    if size >= CRITICAL_BYTES:
        logger.warning(
            "raw payload large kind=%s bytes=%s %s",
            kind,
            size,
            extra,
        )
    elif size >= WARN_BYTES:
        logger.info(
            "raw payload notable kind=%s bytes=%s %s",
            kind,
            size,
            extra,
        )
    return size
