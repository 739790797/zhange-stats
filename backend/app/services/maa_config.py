"""MAA 全托管配置（运维安全上限等）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import now_naive
from app.models.system_config import SystemConfig

MAA_HOST_STATS_KEY = "maa_host_stats"


def get_maa_max_slots(_db: Session | None = None) -> int:
    """运维安全上限：仅环境变量 MAA_MAX_SLOTS，不在管理端配置。"""
    return max(1, int(get_settings().MAA_MAX_SLOTS))


def get_maa_host_stats(db: Session) -> dict[str, Any]:
    row = db.query(SystemConfig).filter(SystemConfig.key == MAA_HOST_STATS_KEY).first()
    if not row or not row.value:
        return {}
    try:
        data = json.loads(row.value)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def set_maa_host_stats(
    db: Session,
    *,
    cpu_percent: str,
    memory_used_mb: str,
    memory_total_mb: str,
    cpu_count: str = "",
) -> dict[str, Any]:
    payload = {
        "cpu_percent": str(cpu_percent or "").strip(),
        "memory_used_mb": str(memory_used_mb or "").strip(),
        "memory_total_mb": str(memory_total_mb or "").strip(),
        "cpu_count": str(cpu_count or "").strip(),
        "reported_at": now_naive().isoformat(timespec="seconds"),
    }
    raw = json.dumps(payload, ensure_ascii=False)
    row = db.query(SystemConfig).filter(SystemConfig.key == MAA_HOST_STATS_KEY).first()
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=MAA_HOST_STATS_KEY, value=raw))
    db.commit()
    return payload
