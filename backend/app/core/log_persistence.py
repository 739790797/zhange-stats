"""JSONL 持久化日志：落盘 + tail 读取。"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, BinaryIO

from app.core.biz_logging import BizTagFilter, record_timestamp
from app.core.config import get_settings
from app.core.log_line import LogLine, filter_log_lines

_FILE_HANDLER: RotatingFileHandler | None = None
_INSTALL_LOCK = threading.Lock()
# 文件行 id = 基数 + 文件内行号（1 起），与环缓冲 id 不重叠
_FILE_ID_BASE = 1_000_000_000
_READ_BLOCK = 256 * 1024
# 单次 tail 最多回读的字节（异常堆栈很长时宁可少给几行）
_TAIL_MAX_BYTES = 16 * 1024 * 1024
_HEAD_FINGERPRINT_BYTES = 256


@dataclass
class _LineCountState:
    path: str = ""
    ino: int = -1
    size: int = 0
    lines: int = 0
    head: bytes = b""


_COUNT_LOCK = threading.Lock()
_COUNT_STATE = _LineCountState()


class _LazyDirRotatingFileHandler(RotatingFileHandler):
    """首条日志才建目录、开文件：仅 import app（如导出 OpenAPI）不在 DATA_DIR 下落盘。"""

    def _open(self):  # type: ignore[override]
        Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
        return super()._open()


class _OncePerRecord(logging.Filter):
    """记录沿 logger 树上传时，挂在多级 logger 上的同一 handler 会被调多次；每条只放行第一次。"""

    def filter(self, record: logging.LogRecord) -> bool:
        seen = record.__dict__.setdefault("_zhange_seen_by", set())
        if id(self) in seen:
            return False
        seen.add(id(self))
        return True


# uvicorn 的日志配置让这两个 logger 不再上传到 root，须单独挂；uvicorn.error、alembic 经 root 收到
_DETACHED_FROM_ROOT = ("uvicorn", "uvicorn.access")


def attach_app_log_handler(handler: logging.Handler) -> None:
    """挂到 root 与 uvicorn 截断上传的 logger。没有 uvicorn 日志配置时它们照常传到 root，靠去重只记一次。"""
    handler.addFilter(_OncePerRecord())
    logging.getLogger().addHandler(handler)
    for name in _DETACHED_FROM_ROOT:
        logging.getLogger(name).addHandler(handler)


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
        settings = get_settings()
        max_bytes = max(1, int(settings.APP_LOG_FILE_MAX_MB)) * 1024 * 1024
        backups = max(1, int(settings.APP_LOG_FILE_BACKUP_COUNT))
        handler = _LazyDirRotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backups,
            encoding="utf-8",
            delay=True,
        )
        handler.setLevel(level)
        handler.setFormatter(JsonLineLogFormatter())
        handler.addFilter(BizTagFilter())
        attach_app_log_handler(handler)
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


def _count_newlines(fh: BinaryIO, start: int, end: int) -> int:
    fh.seek(start)
    remaining = end - start
    total = 0
    while remaining > 0:
        block = fh.read(min(_READ_BLOCK, remaining))
        if not block:
            break
        total += block.count(b"\n")
        remaining -= len(block)
    return total


def _complete_line_count(fh: BinaryIO, path: Path, st: os.stat_result) -> int:
    """[0, st_size) 内完整行数。同一文件只追加时只数新增字节；轮转/截断（inode、大小或文件头变化）才重数。"""
    fh.seek(0)
    head = fh.read(min(st.st_size, _HEAD_FINGERPRINT_BYTES))
    with _COUNT_LOCK:
        state = _COUNT_STATE
        same_file = (
            state.path == str(path)
            and state.ino == st.st_ino
            and st.st_size >= state.size
            and head[: len(state.head)] == state.head
        )
        if same_file:
            if st.st_size > state.size:
                state.lines += _count_newlines(fh, state.size, st.st_size)
        else:
            state.path = str(path)
            state.ino = st.st_ino
            state.lines = _count_newlines(fh, 0, st.st_size)
        state.size = st.st_size
        state.head = head
        return state.lines


def _tail_complete_lines(fh: BinaryIO, end: int, count: int) -> list[bytes]:
    """从 end 往前按块回读，取最后 count 条完整行；末尾还没写完的半行不算。"""
    if count <= 0 or end <= 0:
        return []
    pos = end
    blocks: list[bytes] = []
    newlines = 0
    read_bytes = 0
    while pos > 0 and newlines <= count and read_bytes < _TAIL_MAX_BYTES:
        step = min(_READ_BLOCK, pos)
        pos -= step
        fh.seek(pos)
        block = fh.read(step)
        blocks.append(block)
        newlines += block.count(b"\n")
        read_bytes += len(block)
    data = b"".join(reversed(blocks))
    last_newline = data.rfind(b"\n")
    if last_newline < 0:
        return []
    lines = data[:last_newline].split(b"\n")
    if pos > 0:
        lines = lines[1:]
    return lines[-count:]


def tail_file_logs(
    *,
    limit: int = 400,
    min_level: str | None = None,
    logger_prefix: str | None = None,
    biz_prefix: str | None = None,
    q: str | None = None,
    scan_lines: int = 8000,
    after_id: int = 0,
) -> tuple[str | None, int, list[LogLine]]:
    """返回 (路径, 完整行数, 筛选后的行)。after_id 为上次拿到的文件行 id 时只读其后的新行。"""
    path = resolve_log_file_path()
    if path is None or not path.is_file():
        return (str(path) if path else None, 0, [])

    try:
        with path.open("rb") as fh:
            st = os.fstat(fh.fileno())
            total = _complete_line_count(fh, path, st)
            after_line = after_id - _FILE_ID_BASE if after_id > _FILE_ID_BASE else 0
            if after_line > total:
                # 文件已轮转，旧 id 作废，退回普通 tail
                after_line = 0
            want = max(scan_lines, limit * 4)
            if after_line > 0:
                want = min(want, total - after_line)
            raw_lines = _tail_complete_lines(fh, st.st_size, want)
    except OSError:
        return (str(path), 0, [])

    parsed: list[LogLine] = []
    start_no = total - len(raw_lines) + 1
    for offset, raw in enumerate(raw_lines):
        item = _parse_json_line(raw.decode("utf-8", errors="replace"), start_no + offset)
        if item is not None:
            parsed.append(item)

    filtered = filter_log_lines(
        parsed,
        limit=limit,
        min_level=min_level,
        logger_prefix=logger_prefix,
        biz_prefix=biz_prefix,
        q=q,
        after_id=_FILE_ID_BASE + after_line if after_line > 0 else 0,
    )
    return (str(path), total, filtered)


def file_log_stats() -> tuple[str | None, int, int | None]:
    path = resolve_log_file_path()
    if path is None:
        return (None, 0, None)
    if not path.is_file():
        return (str(path), 0, 0)
    try:
        with path.open("rb") as fh:
            st = os.fstat(fh.fileno())
            lines = _complete_line_count(fh, path, st)
    except OSError:
        return (str(path), 0, None)
    return (str(path), lines, st.st_size)


def reset_line_count_cache_for_tests() -> None:
    global _COUNT_STATE
    with _COUNT_LOCK:
        _COUNT_STATE = _LineCountState()
