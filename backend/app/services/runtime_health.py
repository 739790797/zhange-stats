"""Admin-facing multi-service health snapshot (control plane + 公开运营核对项)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.file_config import default_sqlite_rel, ping_mysql_url, ping_sqlite_path
from app.core.timeutil import now_naive

ServiceStatus = Literal["ok", "degraded", "error", "skipped", "offline"]
OverallStatus = Literal["ok", "degraded", "error"]

_CRED_IN_URL = re.compile(
    r"((?:mysql(?:\+pymysql)?|mariadb|redis|rediss)://)([^@\s]+)@",
    re.I,
)


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


@dataclass
class ConnProbeResult:
    ok: bool
    message: str
    latency_ms: float | None = None


def redact_conn_error(exc: BaseException) -> str:
    """Strip credentials that SQLAlchemy / redis-py sometimes embed in errors."""
    text = str(exc).replace("\n", " ").strip()
    text = _CRED_IN_URL.sub(r"\1***@", text)
    if len(text) > 240:
        text = text[:237] + "..."
    return text or exc.__class__.__name__


def _overall(services: list[ServiceHealthItem]) -> OverallStatus:
    statuses = {s.status for s in services}
    if "error" in statuses:
        return "error"
    if statuses & {"degraded", "offline"}:
        return "degraded"
    return "ok"


def probe_database_settings(*, engine: str, path: str = "", url: str = "") -> ConnProbeResult:
    engine_name = (engine or "").strip().lower()
    t0 = time.perf_counter()
    try:
        if engine_name == "sqlite":
            rel = (path or "").strip() or default_sqlite_rel()
            ping_sqlite_path(Path(rel))
        elif engine_name == "mysql":
            mysql_url = (url or "").strip()
            if not mysql_url.startswith("mysql"):
                return ConnProbeResult(ok=False, message="请填写完整的 MySQL 连接信息")
            ping_mysql_url(mysql_url)
        else:
            return ConnProbeResult(ok=False, message="数据库引擎只能是 sqlite 或 mysql")
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return ConnProbeResult(ok=True, message="连接成功", latency_ms=ms)
    except Exception as exc:  # noqa: BLE001
        return ConnProbeResult(ok=False, message=redact_conn_error(exc))


def probe_redis_url(url: str) -> ConnProbeResult:
    text = (url or "").strip()
    if not text:
        return ConnProbeResult(ok=False, message="请填写主机后再测试")
    t0 = time.perf_counter()
    try:
        import redis

        client = redis.Redis.from_url(
            text,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        try:
            client.ping()
        finally:
            client.close()
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return ConnProbeResult(ok=True, message="连接成功", latency_ms=ms)
    except Exception as exc:  # noqa: BLE001
        return ConnProbeResult(ok=False, message=redact_conn_error(exc))


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
            detail=f"连接失败: {redact_conn_error(exc)}",
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
    result = probe_redis_url(url)
    if result.ok:
        return ServiceHealthItem(
            id="redis",
            name="Redis",
            status="ok",
            latency_ms=result.latency_ms,
            detail="PING ok",
        )
    return ServiceHealthItem(
        id="redis",
        name="Redis",
        status="degraded",
        detail=f"不可用，已降级进程内 KV: {result.message}",
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
