"""业务域日志：统一级别、环缓冲标记与可选请求/任务上下文。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Iterator, TypeVar

from app.core.config import get_settings
from app.core.timeutil import BEIJING

# 与签到/盒子等平台模块名前缀对齐，用于从 logger 名推导 biz 标记
_PLATFORM_PREFIXES: tuple[str, ...] = (
    "skland",
    "taygedo",
    "exilium",
    "kujiequ",
    "mihoyo",
    "steam",
    "minecraft",
    "tarkov",
    "arknights",
    "napcat",
    "pelican",
    "qq",
)

_LOG_CONTEXT: ContextVar[dict[str, str]] = ContextVar("zhange_log_context", default={})
_CONFIGURED = False

F = TypeVar("F", bound=Callable[..., object])


def parse_log_level(name: str | None) -> int:
    token = (name or "INFO").strip().upper()
    return getattr(logging, token, logging.INFO)


def resolve_biz_tag(logger_name: str) -> str:
    """从 logger 名推导稳定业务标记，供平台日志筛选与展示。"""
    name = (logger_name or "").strip()
    if not name:
        return "unknown"

    if name.startswith("zhange."):
        return name[len("zhange.") :]

    if name.startswith("uvicorn"):
        return "infra.http"

    if name.startswith("alembic"):
        return "infra.db"

    parts = name.split(".")
    if len(parts) < 2 or parts[0] != "app":
        return name

    section = parts[1]
    if section == "api" and len(parts) >= 3:
        return f"{parts[2]}.api"

    if section == "core" and len(parts) >= 3:
        return f"core.{parts[2]}"

    if section == "services" and len(parts) >= 3:
        svc = parts[2]
        for platform in _PLATFORM_PREFIXES:
            if svc == platform:
                return platform
            if svc.startswith(f"{platform}_"):
                suffix = svc[len(platform) + 1 :] or "core"
                return f"{platform}.{suffix}"
        if svc == "checkin_orchestrator":
            return "checkin.orchestrator"
        if svc.endswith("_client"):
            return f"upstream.{svc[: -len('_client')]}"
        return f"service.{svc}"

    return name


def format_log_context(ctx: dict[str, str]) -> str:
    if not ctx:
        return ""
    return " ".join(f"{k}={v}" for k, v in sorted(ctx.items()) if v)


@contextmanager
def log_context(**fields: str | int | None) -> Iterator[None]:
    """在 with 块内为日志附加业务上下文（如 platform、member_id）。"""
    normalized = {
        str(k): str(v)
        for k, v in fields.items()
        if v is not None and str(v).strip()
    }
    if not normalized:
        yield
        return
    token = _LOG_CONTEXT.set({**_LOG_CONTEXT.get(), **normalized})
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


def current_log_context() -> dict[str, str]:
    return dict(_LOG_CONTEXT.get())


class BizTagFilter(logging.Filter):
    """为 LogRecord 注入 biz / context 字段，供环缓冲与后续筛选。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.biz_tag = resolve_biz_tag(record.name)  # type: ignore[attr-defined]
        ctx = current_log_context()
        record.log_context = format_log_context(ctx)  # type: ignore[attr-defined]
        return True


def wrap_scheduled_job(job_id: str, func: Callable[[], None]) -> Callable[[], None]:
    """为 APScheduler 任务统一打 job 标记与 begin/done 日志。"""

    sched_logger = logging.getLogger("zhange.scheduler")

    def _wrapped() -> None:
        with log_context(job=job_id):
            sched_logger.info("scheduled job begin id=%s", job_id)
            try:
                func()
            except Exception:
                sched_logger.exception("scheduled job failed id=%s", job_id)
                raise
            else:
                sched_logger.info("scheduled job done id=%s", job_id)

    return _wrapped


def configure_runtime_logging() -> int:
    """提升应用 logger 级别；返回当前有效 logging 级别数值。"""
    global _CONFIGURED
    settings = get_settings()
    level = parse_log_level(settings.APP_LOG_LEVEL)
    logging.getLogger("app").setLevel(level)
    logging.getLogger("zhange").setLevel(level)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # 由 zhange.http 中间件打结构化请求日志，避免与 uvicorn.access 重复
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    if level <= logging.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    _CONFIGURED = True
    return level


def record_timestamp(record: logging.LogRecord) -> str:
    created = datetime.fromtimestamp(record.created, tz=BEIJING)
    return created.strftime("%Y-%m-%d %H:%M:%S")
