"""Admin-facing multi-service health snapshot (control plane + 公开运营核对项)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import text

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


def _probe_database() -> ServiceHealthItem:
    t0 = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return ServiceHealthItem(
            id="database",
            name="数据库",
            status="ok",
            latency_ms=ms,
            detail="SELECT 1 ok",
        )
    except Exception as exc:  # noqa: BLE001
        return ServiceHealthItem(
            id="database",
            name="数据库",
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


def collect_runtime_health() -> RuntimeHealthReport:
    services = [
        _probe_database(),
        _probe_redis(),
    ]
    return RuntimeHealthReport(
        checked_at=now_naive().isoformat(timespec="seconds"),
        overall=_overall(services),
        services=services,
    )
