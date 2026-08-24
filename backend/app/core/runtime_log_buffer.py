"""In-process ring buffer of recent log lines for admin「平台日志」."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Deque

from app.core.biz_logging import BizTagFilter, configure_runtime_logging, record_timestamp
from app.core.config import get_settings
from app.core.log_line import LogLine, filter_log_lines
from app.core.log_persistence import install_file_log_handler

_BUFFER: RuntimeLogBuffer | None = None
_INSTALL_LOCK = threading.Lock()


class RuntimeLogBuffer(logging.Handler):
    """Thread-safe deque of recent formatted log records."""

    def __init__(self, capacity: int = 5000, *, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self.capacity = max(100, int(capacity))
        self._buf: Deque[LogLine] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()
        self._seq = 0
        self.setFormatter(logging.Formatter("%(message)s"))
        self.addFilter(BizTagFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._lock:
                self._seq += 1
                self._buf.append(
                    LogLine(
                        id=self._seq,
                        ts=record_timestamp(record),
                        level=record.levelname,
                        logger=record.name,
                        biz=str(getattr(record, "biz_tag", "") or ""),
                        context=str(getattr(record, "log_context", "") or ""),
                        message=msg,
                    )
                )
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    @property
    def buffered_count(self) -> int:
        with self._lock:
            return len(self._buf)

    def snapshot(
        self,
        *,
        limit: int = 200,
        min_level: str | None = None,
        logger_prefix: str | None = None,
        biz_prefix: str | None = None,
        q: str | None = None,
        after_id: int = 0,
    ) -> tuple[int, list[LogLine]]:
        with self._lock:
            total = len(self._buf)
            rows = list(self._buf)

        filtered = filter_log_lines(
            rows,
            limit=limit,
            min_level=min_level,
            logger_prefix=logger_prefix,
            biz_prefix=biz_prefix,
            q=q,
            after_id=after_id,
        )
        return total, filtered


def get_runtime_log_buffer() -> RuntimeLogBuffer:
    global _BUFFER
    if _BUFFER is None:
        install_runtime_log_buffer()
    assert _BUFFER is not None
    return _BUFFER


def install_runtime_log_buffer(capacity: int | None = None) -> RuntimeLogBuffer:
    """Attach ring-buffer + optional file handlers (idempotent)."""
    global _BUFFER
    with _INSTALL_LOCK:
        if _BUFFER is not None:
            return _BUFFER
        settings = get_settings()
        level = configure_runtime_logging()
        cap = capacity if capacity is not None else settings.APP_LOG_RING_CAPACITY
        handler = RuntimeLogBuffer(capacity=cap, level=level)
        root = logging.getLogger()
        root.addHandler(handler)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "alembic"):
            logging.getLogger(name).addHandler(handler)
        install_file_log_handler(level=level)
        _BUFFER = handler
        return handler
