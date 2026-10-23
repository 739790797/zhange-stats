"""Persist and query bounded, sanitized per-run task logs."""

from __future__ import annotations

import re
import logging
import json
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import func

from app.core.database import SessionLocal
from app.core.biz_logging import current_log_context
from app.core.timeutil import BEIJING
from app.core.timeutil import now_naive
from app.models.job_run_log import JobRunLog

MAX_JOB_RUN_LOGS = 10_000
MAX_JOB_RUN_LOG_LINE_BYTES = 4_096
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|authorization|cookie|api[\s_-]?key|access[\s_-]?key)"
    r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_SECRET_QUERY = re.compile(
    r"(?i)([?&](?:token|key|secret|password|code|authorization)=)[^&\s]+"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_TRUNCATION_MESSAGE = "达到单次执行日志上限，后续日志已省略"


@dataclass(frozen=True)
class JobRunLogEvent:
    level: str
    logger: str
    message: str
    created_at: datetime | None = None


class JobRunLogCaptureHandler(logging.Handler):
    """Buffer app log records for one scheduled run and flush them at completion."""

    def __init__(self, run_id: int) -> None:
        super().__init__(level=logging.INFO)
        self.run_id = run_id
        self._events: list[JobRunLogEvent] = []
        self._lock = threading.Lock()
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        context = current_log_context()
        if str(context.get("job_run_id") or "") != str(self.run_id):
            return
        message = self.format(record)
        if record.exc_info:
            message = f"{message}\n{self.formatter.formatException(record.exc_info)}"
        with self._lock:
            self._events.append(
                JobRunLogEvent(
                    level=record.levelname,
                    logger=record.name,
                    message=message,
                    created_at=datetime.fromtimestamp(
                        record.created, tz=BEIJING
                    ).replace(tzinfo=None),
                )
            )

    def flush_to_store(self) -> int:
        with self._lock:
            events, self._events = self._events, []
        return append_job_run_logs(self.run_id, events)


def sanitize_job_log_message(value: str) -> str:
    message = _ANSI_ESCAPE.sub("", str(value)).replace("\x00", "")
    message = _BEARER_TOKEN.sub("Bearer [已隐藏]", message)
    message = _SECRET_ASSIGNMENT.sub(r"\1\2[已隐藏]", message)
    message = _SECRET_QUERY.sub(r"\1[已隐藏]", message)
    for index, char in enumerate(message):
        if char not in "{[":
            continue
        try:
            json.loads(message[index:])
        except (json.JSONDecodeError, TypeError):
            continue
        message = f"{message[:index]}[结构化上游响应已省略]"
        break
    encoded = message.encode("utf-8")
    if len(encoded) > MAX_JOB_RUN_LOG_LINE_BYTES:
        ellipsis_bytes = len("…".encode("utf-8"))
        message = encoded[: MAX_JOB_RUN_LOG_LINE_BYTES - ellipsis_bytes].decode(
            "utf-8", "ignore"
        ) + "…"
    return message


def append_job_run_logs(run_id: int, events: Iterable[JobRunLogEvent]) -> int:
    rows = [
        JobRunLog(
            run_id=run_id,
            created_at=event.created_at or now_naive(),
            level=event.level.upper()[:16],
            logger=event.logger[:200],
            message=sanitize_job_log_message(event.message),
        )
        for event in events
        if event.message.strip()
    ]
    if not rows:
        return 0

    db = SessionLocal()
    try:
        count = int(
            db.query(func.count(JobRunLog.id))
            .filter(JobRunLog.run_id == run_id)
            .scalar()
            or 0
        )
        already_truncated = (
            db.query(JobRunLog.id)
            .filter(
                JobRunLog.run_id == run_id,
                JobRunLog.is_truncation.is_(True),
            )
            .first()
            is not None
        )
        if already_truncated:
            return 0
        remaining = MAX_JOB_RUN_LOGS - count
        if remaining <= 0:
            rows = []
        elif len(rows) >= remaining:
            rows = rows[: max(0, remaining - 1)]
            rows.append(
                JobRunLog(
                    run_id=run_id,
                    created_at=now_naive(),
                    level="WARNING",
                    logger="zhange.jobs",
                    message=_TRUNCATION_MESSAGE,
                    is_truncation=True,
                )
            )
        db.add_all(rows)
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_job_run_logs(
    run_id: int, *, after_id: int = 0, limit: int = 200
) -> list[JobRunLog]:
    db = SessionLocal()
    try:
        return (
            db.query(JobRunLog)
            .filter(JobRunLog.run_id == run_id, JobRunLog.id > max(0, after_id))
            .order_by(JobRunLog.id.asc())
            .limit(max(1, min(501, limit)))
            .all()
        )
    finally:
        db.close()
