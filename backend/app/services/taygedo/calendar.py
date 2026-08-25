"""塔吉多异环 / 幻塔签到日历解析（本月第 N 天，非公历）。"""

from __future__ import annotations

from typing import Any


def _reward_award(item: dict[str, Any]) -> dict[str, Any]:
    """与今日奖励同源：走 _item_award_dict，保证 icon_url 一致。"""
    # 延迟导入，避免 taygedo_client ↔ attendance ↔ calendar 循环依赖
    from app.services.taygedo.attendance import _item_award_dict

    parsed = _item_award_dict(item)
    if parsed:
        return parsed
    name = str(
        item.get("name")
        or item.get("rewardName")
        or item.get("awardName")
        or "奖励"
    ).strip() or "奖励"
    try:
        count = int(item.get("num") if item.get("num") is not None else item.get("count") or 1)
    except (TypeError, ValueError):
        count = 1
    return {"name": name, "count": count}


def parse_taygedo_attendance_calendar(
    raw: dict[str, Any],
    *,
    fallback_has_today: bool | None = None,
) -> dict[str, Any]:
    """从落库 raw（state + rewards）解析签到周期日历。

    返回:
      claimed_days, total_days, days[{day, claimed, awards}],
      has_today_claim, progress_reliable
    """
    state = raw.get("state") if isinstance(raw.get("state"), dict) else {}
    rewards_raw = raw.get("rewards")
    rewards = (
        [x for x in rewards_raw if isinstance(x, dict)]
        if isinstance(rewards_raw, list)
        else []
    )

    try:
        claimed_days = max(0, int(state.get("days") or 0))
    except (TypeError, ValueError):
        claimed_days = 0
    has_today = bool(state.get("todaySign"))
    if fallback_has_today is True and not has_today:
        has_today = True
        # 本地已签但上游 state 尚未刷新时，至少点亮到 claimed_days+1
        claimed_days = max(claimed_days, 1) if claimed_days == 0 else claimed_days

    days_out: list[dict[str, Any]] = []
    for idx, item in enumerate(rewards):
        day = idx + 1
        days_out.append(
            {
                "day": day,
                "claimed": day <= claimed_days,
                "awards": [_reward_award(item)],
            }
        )

    return {
        "claimed_days": claimed_days,
        "total_days": len(days_out),
        "has_today_claim": has_today,
        "progress_reliable": True,
        "days": days_out,
    }
