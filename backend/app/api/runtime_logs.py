"""Admin APIs: in-process runtime log ring buffer + persistent JSONL tail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.deps import require_admin
from app.core.log_line import LogLine, merge_log_lines
from app.core.log_persistence import file_log_stats, tail_file_logs
from app.core.runtime_log_buffer import get_runtime_log_buffer
from app.models.user import User

router = APIRouter(prefix="/settings/runtime-logs", tags=["settings"])


class RuntimeLogLineOut(BaseModel):
    id: int
    ts: str
    level: str
    logger: str
    biz: str = ""
    context: str = ""
    message: str


class RuntimeLogsOut(BaseModel):
    capacity: int
    buffered: int
    source: str = "ring"
    file_path: str | None = None
    file_lines: int | None = None
    file_bytes: int | None = None
    lines: list[RuntimeLogLineOut] = Field(default_factory=list)


class RuntimeLogsClearOut(BaseModel):
    ok: bool = True
    message: str = "已清空内存日志缓冲"


def _to_out(line: LogLine) -> RuntimeLogLineOut:
    return RuntimeLogLineOut(
        id=line.id,
        ts=line.ts,
        level=line.level,
        logger=line.logger,
        biz=line.biz,
        context=line.context,
        message=line.message,
    )


@router.get("", response_model=RuntimeLogsOut)
def get_runtime_logs(
    _: User = Depends(require_admin),
    limit: int = Query(default=300, ge=1, le=1000),
    level: str | None = Query(
        default=None,
        description="最低级别：DEBUG / INFO / WARNING / ERROR / CRITICAL",
    ),
    logger: str | None = Query(default=None, description="logger 名前缀，如 zhange"),
    biz: str | None = Query(default=None, description="业务标记前缀，如 skland / checkin"),
    q: str | None = Query(default=None, description="消息或 logger 子串"),
    after_id: int = Query(default=0, ge=0, description="仅返回 id 大于该值的新行"),
    source: str = Query(
        default="all",
        description="ring=内存环缓冲；file=持久化 JSONL；all=合并（推荐）",
    ),
) -> RuntimeLogsOut:
    buf = get_runtime_log_buffer()
    file_path, file_line_count, file_bytes = file_log_stats()
    mode = (source or "all").strip().lower()
    if mode not in {"ring", "file", "all"}:
        mode = "all"

    ring_lines: list[LogLine] = []
    file_lines: list[LogLine] = []
    if mode in {"ring", "all"}:
        _, ring_lines = buf.snapshot(
            limit=limit if mode == "ring" else max(limit, 800),
            min_level=level,
            logger_prefix=logger,
            biz_prefix=biz,
            q=q,
            after_id=after_id if mode == "ring" else 0,
        )
    if mode in {"file", "all"}:
        _, _, file_lines = tail_file_logs(
            limit=limit if mode == "file" else max(limit, 1200),
            min_level=level,
            logger_prefix=logger,
            biz_prefix=biz,
            q=q,
        )

    if mode == "ring":
        lines = ring_lines
    elif mode == "file":
        lines = file_lines
    else:
        lines = merge_log_lines(ring_lines, file_lines, limit=limit)

    buffered_total = buf.buffered_count
    return RuntimeLogsOut(
        capacity=buf.capacity,
        buffered=buffered_total,
        source=mode,
        file_path=file_path,
        file_lines=file_line_count,
        file_bytes=file_bytes,
        lines=[_to_out(x) for x in lines],
    )
