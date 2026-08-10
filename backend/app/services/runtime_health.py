"""Admin-facing multi-service health snapshot (control plane deps + MAA)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.core.timeutil import now_naive
from app.services.maa_config import get_maa_host_stats
from app.services.maa_slots import resource_summary

ServiceStatus = Literal["ok", "degraded", "error", "skipped", "offline"]
OverallStatus = Literal["ok", "degraded", "error"]

DEFAULT_MAA_STALE_SEC = 30


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


def maa_stale_threshold_sec() -> int:
    """Worker host-stats older than this → offline (poll_sec * 3, min 15)."""
    raw = (os.environ.get("MAA_WORKER_POLL_SEC") or "").strip()
    try:
        poll = int(raw) if raw else 5
    except ValueError:
        poll = 5
    return max(15, poll * 3, DEFAULT_MAA_STALE_SEC)


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
        return ServiceHealthItem(
            id="redis",
            name="Redis",
            status="skipped",
            detail="未配置 REDIS_URL，短时 KV 使用进程内内存",
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


def _parse_reported_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text_val = str(raw).strip()
    if not text_val:
        return None
    try:
        return datetime.fromisoformat(text_val)
    except ValueError:
        return None


def _probe_maa_worker(db: Session) -> ServiceHealthItem:
    settings = get_settings()
    host = get_maa_host_stats(db)
    reported = _parse_reported_at(host.get("reported_at"))
    threshold = maa_stale_threshold_sec()
    now = now_naive()

    if reported is None:
        if settings.MAA_ENABLED:
            return ServiceHealthItem(
                id="maa_worker",
                name="MAA Worker",
                status="offline",
                detail=f"已启用但从未上报宿主机状态（阈值 {threshold}s）",
            )
        return ServiceHealthItem(
            id="maa_worker",
            name="MAA Worker",
            status="skipped",
            detail="未启用 / 尚无 Worker 上报",
        )

    age = (now - reported).total_seconds()
    if age < 0:
        age = 0.0
    if age <= threshold:
        cpu = host.get("cpu_percent") or "—"
        return ServiceHealthItem(
            id="maa_worker",
            name="MAA Worker",
            status="ok",
            detail=f"宿主机心跳 {int(age)}s 前 · CPU {cpu}%",
        )
    return ServiceHealthItem(
        id="maa_worker",
        name="MAA Worker",
        status="offline",
        detail=f"宿主机心跳已过期（{int(age)}s > {threshold}s）",
    )


def _probe_maa_slots(db: Session) -> ServiceHealthItem:
    summary = resource_summary(db)
    online = int(summary.get("online") or 0)
    offline = int(summary.get("offline") or 0)
    error = int(summary.get("error") or 0)
    busy = int(summary.get("busy") or 0)
    active = int(summary.get("active_slots") or 0)
    detail = (
        f"活跃 {active}/{summary.get('max_slots')} · "
        f"online {online} / offline {offline} / error {error} / busy {busy}"
    )
    if active == 0 and not get_settings().MAA_ENABLED:
        return ServiceHealthItem(
            id="maa_slots",
            name="MAA 槽位",
            status="skipped",
            detail=detail,
        )
    if error > 0:
        return ServiceHealthItem(
            id="maa_slots",
            name="MAA 槽位",
            status="degraded",
            detail=detail,
        )
    return ServiceHealthItem(
        id="maa_slots",
        name="MAA 槽位",
        status="ok",
        detail=detail,
    )


def collect_runtime_health(
    db: Session,
    *,
    scheduler_running: bool,
) -> RuntimeHealthReport:
    services = [
        _probe_app(),
        _probe_mysql(),
        _probe_redis(),
        _probe_scheduler(running=scheduler_running),
        _probe_maa_worker(db),
        _probe_maa_slots(db),
    ]
    return RuntimeHealthReport(
        checked_at=now_naive().isoformat(timespec="seconds"),
        overall=_overall(services),
        services=services,
    )
