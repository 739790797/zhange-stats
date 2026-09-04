"""Admin-facing multi-service health snapshot (control plane + 公开运营核对项)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.core.timeutil import now_naive

ServiceStatus = Literal["ok", "degraded", "error", "skipped", "offline"]
OverallStatus = Literal["ok", "degraded", "error"]


@dataclass
class ServiceHealthItem:
    id: str
    name: str
    status: ServiceStatus
    latency_ms: float | None = None
    detail: str = ""


@dataclass
class RuntimeHealthReport:
    checked_at: str
    overall: OverallStatus
    services: list[ServiceHealthItem] = field(default_factory=list)


def _overall(services: list[ServiceHealthItem]) -> OverallStatus:
    statuses = {s.status for s in services}
    if "error" in statuses:
        return "error"
    if statuses & {"degraded", "offline"}:
        return "degraded"
    return "ok"


def _probe_app() -> ServiceHealthItem:
    settings = get_settings()
    return ServiceHealthItem(
        id="app",
        name="控制面",
        status="ok",
        detail=f"v{settings.APP_VERSION} · {settings.APP_ENV}",
    )


def _probe_mysql() -> ServiceHealthItem:
    t0 = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return ServiceHealthItem(
            id="mysql",
            name="MySQL",
            status="ok",
            latency_ms=ms,
            detail="SELECT 1 ok",
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceHealthItem(
            id="mysql",
            name="MySQL",
            status="error",
            detail=f"连接失败: {exc}",
        )


def _probe_redis() -> ServiceHealthItem:
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        prod = bool(settings.is_production)
        return ServiceHealthItem(
            id="redis",
            name="Redis",
            status="degraded" if prod else "skipped",
            detail="未配置 REDIS_URL，短时 KV / 限流使用进程内内存",
        )
    t0 = time.perf_counter()
    try:
        import redis

        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return ServiceHealthItem(
            id="redis",
            name="Redis",
            status="ok",
            latency_ms=ms,
            detail="PING ok",
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceHealthItem(
            id="redis",
            name="Redis",
            status="degraded",
            detail=f"不可用，已降级进程内 KV: {exc}",
        )


def _probe_scheduler(*, running: bool) -> ServiceHealthItem:
    if running:
        return ServiceHealthItem(
            id="scheduler",
            name="调度器",
            status="ok",
            detail="APScheduler running",
        )
    return ServiceHealthItem(
        id="scheduler",
        name="调度器",
        status="degraded",
        detail="APScheduler 未运行",
    )


def _probe_app_env() -> ServiceHealthItem:
    settings = get_settings()
    env = (settings.APP_ENV or "").strip() or "unknown"
    if settings.is_production:
        return ServiceHealthItem(
            id="app_env",
            name="运行环境",
            status="ok",
            detail="APP_ENV=production",
        )
    return ServiceHealthItem(
        id="app_env",
        name="运行环境",
        status="skipped",
        detail=f"当前 {env}；公开引流须 production",
    )


def _probe_xff() -> ServiceHealthItem:
    settings = get_settings()
    if settings.TRUST_X_FORWARDED_FOR:
        return ServiceHealthItem(
            id="xff",
            name="X-Forwarded-For",
            status="ok",
            detail="已信任；仅应在受信反代后开启",
        )
    return ServiceHealthItem(
        id="xff",
        name="X-Forwarded-For",
        status="skipped",
        detail="未信任；反代后须设 TRUST_X_FORWARDED_FOR=true，否则限流按连接 IP",
    )


def _probe_smtp(db: Session) -> ServiceHealthItem:
    from app.services.email_config import load_email_config, public_email_config

    cfg = public_email_config(load_email_config(db))
    if cfg.get("configured"):
        return ServiceHealthItem(
            id="smtp",
            name="SMTP",
            status="ok",
            detail="邮箱验证码可发送",
        )
    if get_settings().is_production:
        return ServiceHealthItem(
            id="smtp",
            name="SMTP",
            status="degraded",
            detail="生产未配可用 SMTP，公开注册发不出验证码",
        )
    return ServiceHealthItem(
        id="smtp",
        name="SMTP",
        status="skipped",
        detail="未配置 SMTP",
    )


def collect_runtime_health(
    _db: Session,
    *,
    scheduler_running: bool,
) -> RuntimeHealthReport:
    services = [
        _probe_app(),
        _probe_mysql(),
        _probe_redis(),
        _probe_scheduler(running=scheduler_running),
        _probe_app_env(),
        _probe_xff(),
        _probe_smtp(_db),
    ]
    return RuntimeHealthReport(
        checked_at=now_naive().isoformat(timespec="seconds"),
        overall=_overall(services),
        services=services,
    )
