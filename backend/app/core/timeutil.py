"""项目统一时间：业务与展示一律使用北京时间（Asia/Shanghai）。

约定：
- 业务库 DATETIME 存北京墙钟（无 tzinfo）
- JWT 等少数协议字段仍用 UTC（见 security / openid）
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc

# 兼容旧名
TZ = BEIJING


def now() -> datetime:
    """当前北京时间（aware）。"""
    return datetime.now(BEIJING)


def now_naive() -> datetime:
    """写入 MySQL DATETIME 的当前北京墙钟。"""
    return now().replace(tzinfo=None)


def today() -> date:
    """今天的北京日期。"""
    return now().date()


def ensure(dt: datetime) -> datetime:
    """把库内/外部时间规范为北京 aware；naive 视为北京墙钟。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING)
    return dt.astimezone(BEIJING)


def to_naive(dt: datetime) -> datetime:
    """比较/写入用的北京 naive。"""
    return ensure(dt).replace(tzinfo=None)


def day_bounds(d: date) -> tuple[datetime, datetime]:
    """北京自然日 [00:00, 次日 00:00)。"""
    start = datetime(d.year, d.month, d.day, tzinfo=BEIJING)
    return start, start + timedelta(days=1)


def utc_now() -> datetime:
    """仅用于 JWT / OpenID 等协议。"""
    return datetime.now(UTC)
