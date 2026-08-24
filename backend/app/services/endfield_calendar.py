"""森空岛终末地签到日历解析（周期第 N 天，非公历）。"""

from __future__ import annotations

from typing import Any

from app.services.checkin_common import award_item


def _award_from_map(
    resource_map: dict[str, Any],
    award_id: str,
) -> list[dict[str, Any]]:
    if not award_id:
        return []
    res = resource_map.get(award_id) or resource_map.get(str(award_id))
    if not isinstance(res, dict):
        return []
    name = str(res.get("name") or "奖励").strip() or "奖励"
    try:
        count = int(res.get("count") or 1)
    except (TypeError, ValueError):
        count = 1
    icon = res.get("icon") or res.get("iconUrl") or res.get("icon_url")
    icon_url = str(icon).strip() if icon else None
    return [
        award_item(
            name=name,
            count=count,
            resource_id=award_id,
            resource_type=res.get("type"),
            icon_url=icon_url,
        )
    ]


def parse_endfield_attendance_calendar(
    resp: dict[str, Any],
    *,
    fallback_has_today: bool | None = None,
) -> dict[str, Any]:
    """从 GET endfield/attendance 响应解析签到日历。

    上游 calendar 项为 {awardId, done, available}，奖励详情在 resourceInfoMap。
    """
    empty = {
        "claimed_days": 0,
        "total_days": 0,
        "days": [],
        "has_today_claim": False,
        "progress_reliable": False,
    }
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    if resp.get("code") != 0 or not data:
        return dict(empty)

    resource_map = data.get("resourceInfoMap") or {}
    if not isinstance(resource_map, dict):
        resource_map = {}

    calendar = data.get("calendar")
    cells: list[Any] = []
    if isinstance(calendar, list):
        cells = calendar
    elif isinstance(calendar, dict):
        keys = sorted(
            (k for k in calendar.keys() if str(k).isdigit()),
            key=lambda k: int(k),
        )
        cells = [calendar[k] for k in keys]

    if not cells:
        return dict(empty)

    days_out: list[dict[str, Any]] = []
    for idx, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue
        day_no = idx + 1
        award_id = str(cell.get("awardId") or cell.get("id") or "").strip()
        awards = _award_from_map(resource_map, award_id)
        days_out.append(
            {
                "day": day_no,
                "claimed": bool(cell.get("done")),
                "awards": awards,
            }
        )

    claimed_days = sum(1 for d in days_out if d.get("claimed"))
    has_today = data.get("hasToday")
    if has_today is None:
        has_today_claim = bool(fallback_has_today)
    else:
        has_today_claim = bool(has_today)

    return {
        "claimed_days": claimed_days,
        "total_days": len(days_out),
        "days": days_out,
        "has_today_claim": has_today_claim,
        "progress_reliable": True,
    }
