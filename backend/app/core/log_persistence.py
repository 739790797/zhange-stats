"""JSONL 持久化日志：落盘 + tail 读取。"""

from __future__ import annotations

import json
import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.biz_logging import BizTagFilter, record_timestamp
from app.core.config import get_settings
from app.core.log_line import LogLine, filter_log_lines

_FILE_HANDLER: RotatingFileHandler | None = None
_INSTALL_LOCK = threading.Lock()
_FILE_ID_BASE = 1_000_000_000


class JsonLineLogFormatter(logging.Formatter):
    """结构化 JSONL，便于 tail 解析与 grep。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": record_timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "biz": str(getattr(record, "biz_tag", "") or ""),
            "context": str(getattr(record, "log_context", "") or ""),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def resolve_log_file_path() -> Path | None:
    settings = get_settings()
    if not settings.APP_LOG_FILE:
        return None
    return settings.data_dir_path / "logs" / "app.jsonl"


def install_file_log_handler(*, level: int) -> RotatingFileHandler | None:
    global _FILE_HANDLER
    path = resolve_log_file_path()
    if path is None:
        return None
    with _INSTALL_LOCK:
        if _FILE_HANDLER is not None:
            return _FILE_HANDLER
        path.parent.mkdir(parents=True, exist_ok=True)
        settings = get_settings()
        max_bytes = max(1, int(settings.APP_LOG_FILE_MAX_MB)) * 1024 * 1024
        backups = max(1, int(settings.APP_LOG_FILE_BACKUP_COUNT))
        handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backups,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(JsonLineLogFormatter())
        handler.addFilter(BizTagFilter())
        root = logging.getLogger()
        root.addHandler(handler)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "alembic"):
            logging.getLogger(name).addHandler(handler)
        _FILE_HANDLER = handler
        return handler


def _parse_json_line(raw: str, line_no: int) -> LogLine | None:
    text = raw.strip()
    if not text:
        return None
    try:
        row: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return None
    message = str(row.get("message") or "")
    exc = row.get("exc")
    if exc:
        message = f"{message}\n{exc}" if message else str(exc)
    return LogLine(
        id=_FILE_ID_BASE + line_no,
        ts=str(row.get("ts") or ""),
        level=str(row.get("level") or "INFO").upper(),
        logger=str(row.get("logger") or ""),
        biz=str(row.get("biz") or ""),
        context=str(row.get("context") or ""),
        message=message,
    )


def tail_file_logs(
    *,
    limit: int = 400,
    min_level: str | None = None,
    logger_prefix: str | None = None,
    biz_prefix: str | None = None,
    q: str | None = None,
    scan_lines: int = 8000,
) -> tuple[str | None, int, list[LogLine]]:
    path = resolve_log_file_path()
    if path is None or not path.is_file():
        return (str(path) if path else None, 0, [])

    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return (str(path), 0, [])

    total = len(lines)
    chunk = lines[-max(scan_lines, limit * 4) :]
    parsed: list[LogLine] = []
    start_no = total - len(chunk) + 1
    for offset, raw in enumerate(chunk):
        item = _parse_json_line(raw, start_no + offset)
        if item is not None:
            parsed.append(item)

    filtered = filter_log_lines(
        parsed,
        limit=limit,
        min_level=min_level,
        logger_prefix=logger_prefix,
        biz_prefix=biz_prefix,
        q=q,
    )
    return (str(path), total, filtered)


def file_log_stats() -> tuple[str | None, int, int | None]:
    path = resolve_log_file_path()
    if path is None:
        return (None, 0, None)
    if not path.is_file():
        return (str(path), 0, 0)
    try:
        size = path.stat().st_size
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = sum(1 for _ in fh)
    except OSError:
        return (str(path), 0, None)
    return (str(path), lines, size)
