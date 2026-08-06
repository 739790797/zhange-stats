"""森空岛明日方舟签到日历解析（周期第 N 天，非公历）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.timeutil import BEIJING
from app.services.skland_awards import (
    award_dict,
    award_from_resource,
    format_award_items,
    ts_is_beijing_day,
)


def _beijing_month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """当前北京月的 [start, next_month_start)。"""
    if now is None:
        now = datetime.now(tz=BEIJING)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=BEIJING)
    else:
        now = now.astimezone(BEIJING)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _ts_in_beijing_month(ts: Any, *, month_start: datetime, month_end: datetime) -> bool:
    try:
        value = int(ts)
    except (TypeError, ValueError):
        return False
    if value > 10_000_000_000:
        value //= 1000
    try:
        dt = datetime.fromtimestamp(value, tz=BEIJING)
    except (OverflowError, OSError, ValueError):
        return False
    return month_start <= dt < month_end


def count_claims_this_month(records: list[Any], *, now: datetime | None = None) -> int:
    """本北京月领取天数（同一天 first+daily 只计 1）。"""
    if not isinstance(records, list):
        return 0
    start, end = _beijing_month_bounds(now)
    days: set[Any] = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not _ts_in_beijing_month(rec.get("ts"), month_start=start, month_end=end):
            continue
        try:
            value = int(rec.get("ts"))
        except (TypeError, ValueError):
            continue
        if value > 10_000_000_000:
            value //= 1000
        try:
            days.add(datetime.fromtimestamp(value, tz=BEIJING).date())
        except (OverflowError, OSError, ValueError):
            continue
    return len(days)


def _cell_awards(
    cell: Any,
    resource_map: dict[str, Any],
) -> list[dict[str, Any]]:
    """解析单日格子里的奖励列表。"""
    if cell is None:
        return []
    # 单格可能是奖励数组
    if isinstance(cell, list):
        text, items = format_award_items(cell, with_icons=True)
        if items:
            return items
        # 列表元素也可能是 resourceId / 简写对象
        out: list[dict[str, Any]] = []
        for el in cell:
            out.extend(_cell_awards(el, resource_map))
        return out

    if not isinstance(cell, dict):
        return []

    # 嵌套 awards
    if isinstance(cell.get("awards"), list):
        _, items = format_award_items(cell["awards"], with_icons=True)
        if items:
            return items

    # 直接带 resource
    if isinstance(cell.get("resource"), dict):
        _, items = format_award_items([cell], with_icons=True)
        if items:
            return items

    rid = (
        cell.get("resourceId")
        or cell.get("awardId")
        or cell.get("id")
    )
    parsed = award_from_resource(
        resource_map, rid, cell.get("count"), with_icon=True
    )
    if parsed:
        # 格子上可能自带 type
        if not parsed.get("resource_type") and cell.get("type"):
            parsed = award_dict(
                name=parsed["name"],
                count=parsed["count"],
                resource_id=parsed.get("resource_id"),
                resource_type=cell.get("type"),
                with_icon=True,
            )
        return [parsed]

    # 无 map：用格子自身 name/type
    name = str(cell.get("name") or "").strip()
    rtype = cell.get("type") or cell.get("resourceType")
    if name or rtype:
        try:
            qty = int(cell.get("count") or 1)
        except (TypeError, ValueError):
            qty = 1
        return [
            award_dict(
                name=name or "奖励",
                count=qty,
                resource_id=rid,
                resource_type=rtype,
                with_icon=True,
            )
        ]
    return []


def _cell_explicit_claimed(cell: Any) -> bool | None:
    """格子自带领取态时返回 True/False，否则 None（交给天数推断）。"""
    if not isinstance(cell, dict):
        return None
    for key in ("done", "received", "claimed", "finished"):
        if key in cell:
            return bool(cell.get(key))
    status = cell.get("status")
    if status is None:
        return None
    if isinstance(status, bool):
        return status
    if isinstance(status, (int, float)):
        return int(status) > 0
    s = str(status).strip().lower()
    if s in ("done", "received", "claimed", "ok", "1", "true"):
        return True
    if s in ("0", "false", "pending", "none", ""):
        return False
    return None


def _calendar_progress_reliable(cells: list[Any], records: list[Any]) -> bool:
    """上游进度是否可信。

    B 服等渠道可能返回带 done=false 的完整日历但 records 为空，
    此时不能把「全未签」当真（POST 仍可能返回请勿重复签到）。
    """
    if any(isinstance(rec, dict) for rec in records):
        return True
    return any(
        isinstance(cell, dict) and cell.get("done") is True for cell in cells
    )


def apply_claimed_days(
    days_out: list[dict[str, Any]], claimed_days: int
) -> list[dict[str, Any]]:
    """按已签天数点亮前 N 格（保留 awards）。"""
    n = max(0, int(claimed_days))
    for d in days_out:
        d["claimed"] = int(d.get("day") or 0) <= n
    return days_out


def _award_fingerprint(awards: list[dict[str, Any]]) -> tuple[tuple[str, int], ...]:
    items: list[tuple[str, int]] = []
    for a in awards:
        if not isinstance(a, dict):
            continue
        rid = str(a.get("resource_id") or "").strip()
        name = str(a.get("name") or "").strip()
        key = rid or name
        if not key:
            continue
        try:
            count = int(a.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        items.append((key, count))
    return tuple(sorted(items))


def infer_claimed_day_from_awards(
    days_out: list[dict[str, Any]],
    awards: list[dict[str, Any]] | None,
) -> int | None:
    """用今日奖励唯一匹配到周期第 N 天时，推断已签到第 N 天。"""
    target = _award_fingerprint(awards or [])
    if not target:
        return None
    hits = [
        int(d["day"])
        for d in days_out
        if _award_fingerprint(d.get("awards") or []) == target
    ]
    if len(hits) != 1:
        return None
    return hits[0]


def parse_arknights_attendance_calendar(
    resp: dict[str, Any],
    *,
    now: datetime | None = None,
    fallback_has_today: bool | None = None,
    fallback_today_awards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """从 GET attendance 响应解析签到日历。

    返回:
      claimed_days, total_days, days[{day, claimed, awards}],
      has_today_claim, raw_calendar_type, progress_reliable
    """
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    if resp.get("code") != 0 or not data:
        return {
            "claimed_days": 0,
            "total_days": 0,
            "days": [],
            "has_today_claim": False,
            "raw_calendar_type": None,
            "progress_reliable": False,
        }

    resource_map = data.get("resourceInfoMap") or {}
    if not isinstance(resource_map, dict):
        resource_map = {}

    calendar = data.get("calendar")
    raw_type: str | None
    cells: list[Any]
    if isinstance(calendar, list):
        cells = calendar
        raw_type = "list"
    elif isinstance(calendar, dict):
        keys = sorted(
            (k for k in calendar.keys() if str(k).isdigit()),
            key=lambda k: int(k),
        )
        cells = [calendar[k] for k in keys]
        raw_type = "dict"
    else:
        cells = []
        raw_type = type(calendar).__name__ if calendar is not None else None

    records = data.get("records") or []
    if not isinstance(records, list):
        records = []
    claimed_by_records = count_claims_this_month(records, now=now)
    reliable = _calendar_progress_reliable(cells, records)

    from app.core.timeutil import today as beijing_today

    day = beijing_today()
    has_today = any(
        isinstance(rec, dict) and ts_is_beijing_day(rec.get("ts"), day)
        for rec in records
    )

    days_out: list[dict[str, Any]] = []
    for idx, cell in enumerate(cells):
        day_no = idx + 1
        awards = _cell_awards(cell, resource_map)
        if reliable:
            explicit = _cell_explicit_claimed(cell)
            if explicit is not None:
                claimed = explicit
            else:
                claimed = day_no <= claimed_by_records
        else:
            claimed = False
        days_out.append(
            {
                "day": day_no,
                "claimed": claimed,
                "awards": awards,
            }
        )

    if reliable:
        claimed_days = claimed_by_records
        if days_out and any(_cell_explicit_claimed(c) is True for c in cells):
            claimed_days = sum(1 for d in days_out if d["claimed"])
        elif claimed_days > len(days_out) > 0:
            claimed_days = len(days_out)
    else:
        # 上游无进度（常见 B 服）：不用本地签到天数冒充周期第 N 天
        claimed_days = 0
        inferred = infer_claimed_day_from_awards(days_out, fallback_today_awards)
        if inferred is not None:
            claimed_days = inferred
            apply_claimed_days(days_out, claimed_days)
            has_today = True
        if fallback_has_today is True:
            has_today = True

    return {
        "claimed_days": claimed_days,
        "total_days": len(days_out),
        "days": days_out,
        "has_today_claim": has_today,
        "raw_calendar_type": raw_type,
        "progress_reliable": reliable,
    }
