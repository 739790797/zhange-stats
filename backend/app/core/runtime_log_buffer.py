"""In-process ring buffer of recent log lines for admin「平台日志」."""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque

from app.core.timeutil import BEIJING

_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_BUFFER: RuntimeLogBuffer | None = None
_INSTALL_LOCK = threading.Lock()


@dataclass(frozen=True)
class LogLine:
    id: int
    ts: str
    level: str
    logger: str
    message: str


class RuntimeLogBuffer(logging.Handler):
    """Thread-safe deque of recent formatted log records."""

    def __init__(self, capacity: int = 3000) -> None:
        super().__init__(level=logging.INFO)
        self.capacity = max(100, int(capacity))
        self._buf: Deque[LogLine] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()
        self._seq = 0
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            created = datetime.fromtimestamp(record.created, tz=BEIJING)
            with self._lock:
                self._seq += 1
                self._buf.append(
                    LogLine(
                        id=self._seq,
                        ts=created.strftime("%Y-%m-%d %H:%M:%S"),
                        level=record.levelname,
                        logger=record.name,
                        message=msg,
                    )
                )
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def snapshot(
        self,
        *,
        limit: int = 200,
        min_level: str | None = None,
        logger_prefix: str | None = None,
        q: str | None = None,
        after_id: int = 0,
    ) -> tuple[int, list[LogLine]]:
        limit = max(1, min(int(limit), 1000))
        min_num = _LEVEL_ORDER.get((min_level or "").upper()) if min_level else None
        prefix = (logger_prefix or "").strip()
        needle = (q or "").strip().lower()
        after = max(0, int(after_id or 0))

        with self._lock:
            total = len(self._buf)
            rows = list(self._buf)

        out: list[LogLine] = []
        for line in rows:
            if line.id <= after:
                continue
            if min_num is not None and _LEVEL_ORDER.get(line.level, 0) < min_num:
                continue
            if prefix and not (
                line.logger == prefix or line.logger.startswith(f"{prefix}.")
            ):
                continue
            if needle and needle not in line.message.lower() and needle not in line.logger.lower():
                continue
            out.append(line)

        if after <= 0:
            out = out[-limit:]
        else:
            out = out[:limit]
        return total, out


def get_runtime_log_buffer() -> RuntimeLogBuffer:
    global _BUFFER
    if _BUFFER is None:
        install_runtime_log_buffer()
    assert _BUFFER is not None
    return _BUFFER


def install_runtime_log_buffer(capacity: int = 3000) -> RuntimeLogBuffer:
    """Attach a shared ring-buffer handler (idempotent)."""
    global _BUFFER
    with _INSTALL_LOCK:
        if _BUFFER is not None:
            return _BUFFER
        handler = RuntimeLogBuffer(capacity=capacity)
        root = logging.getLogger()
        root.addHandler(handler)
        # uvicorn / alembic often set propagate=False
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "alembic"):
            logging.getLogger(name).addHandler(handler)
        _BUFFER = handler
        return handler
