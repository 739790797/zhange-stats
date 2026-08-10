"""Admin APIs: in-process runtime log ring buffer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.deps import require_admin
from app.core.runtime_log_buffer import get_runtime_log_buffer
from app.models.user import User

router = APIRouter(prefix="/settings/runtime-logs", tags=["settings"])


class RuntimeLogLineOut(BaseModel):
    id: int
    ts: str
    level: str
    logger: str
    message: str


class RuntimeLogsOut(BaseModel):
    capacity: int
    buffered: int
    lines: list[RuntimeLogLineOut] = Field(default_factory=list)


class RuntimeLogsClearOut(BaseModel):
    ok: bool = True
    message: str = "已清空内存日志缓冲"


@router.get("", response_model=RuntimeLogsOut)
def get_runtime_logs(
    _: User = Depends(require_admin),
    limit: int = Query(default=300, ge=1, le=1000),
    level: str | None = Query(
        default=None,
        description="最低级别：DEBUG / INFO / WARNING / ERROR / CRITICAL",
    ),
    logger: str | None = Query(default=None, description="logger 名前缀，如 zhange"),
    q: str | None = Query(default=None, description="消息或 logger 子串"),
    after_id: int = Query(default=0, ge=0, description="仅返回 id 大于该值的新行"),
) -> RuntimeLogsOut:
    buf = get_runtime_log_buffer()
    buffered, lines = buf.snapshot(
        limit=limit,
        min_level=level,
        logger_prefix=logger,
        q=q,
        after_id=after_id,
    )
    return RuntimeLogsOut(
        capacity=buf.capacity,
        buffered=buffered,
        lines=[
            RuntimeLogLineOut(
                id=x.id,
                ts=x.ts,
                level=x.level,
                logger=x.logger,
                message=x.message,
            )
            for x in lines
        ],
    )


@router.post("/clear", response_model=RuntimeLogsClearOut)
def clear_runtime_logs(_: User = Depends(require_admin)) -> RuntimeLogsClearOut:
    get_runtime_log_buffer().clear()
    return RuntimeLogsClearOut()
