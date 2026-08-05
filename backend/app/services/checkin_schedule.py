"""用户级每日签到时间（北京时间 HH:MM）。"""

from __future__ import annotations

from typing import Any


def clamp_checkin_hour(value: Any, default: int = 0) -> int:
    try:
        return max(0, min(23, int(value)))
    except (TypeError, ValueError):
        return default


def clamp_checkin_minute(value: Any, default: int = 5) -> int:
    try:
        return max(0, min(59, int(value)))
    except (TypeError, ValueError):
        return default
