"""库街区鸣潮 / 战双签到日历解析（本月第 N 天，非公历）。"""

from __future__ import annotations

from typing import Any

from app.services.checkin.common import award_item


def _config_awards(item: dict[str, Any]) -> list[dict[str, Any]]:
    name = str(
        item.get("goodsName")
        or item.get("goods_name")
        or item.get("name")
        or ""
    ).strip()
    if not name:
        name = "奖励"
    num = item.get("goodsNum")
    if num is None:
        num = item.get("count")
    try:
        count = int(num) if num is not None else 1
    except (TypeError, ValueError):
        count = 1
    rid = item.get("goodsId") or item.get("goodsID") or item.get("id")
    icon = str(item.get("goodsUrl") or item.get("goods_url") or "").strip() or None
    return [
        award_item(
            name=name,
            count=count,
            resource_id=rid,
            resource_type=item.get("typeName") or item.get("type"),
            icon_url=icon,
        )
    ]


def parse_kujiequ_attendance_calendar(
    raw: dict[str, Any],
    *,
    fallback_has_today: bool | None = None,
) -> dict[str, Any]:
    """从落库 raw（init + records）解析签到周期日历。

    返回:
      claimed_days, total_days, days[{day, claimed, awards}],
      has_today_claim, progress_reliable
    """
    init = raw.get("init") if isinstance(raw.get("init"), dict) else {}
    configs_raw = init.get("signInGoodsConfigs")
    configs = (
        [x for x in configs_raw if isinstance(x, dict)]
        if isinstance(configs_raw, list)
        else []
    )

    try:
        claimed_days = max(0, int(init.get("sigInNum") or 0))
    except (TypeError, ValueError):
        claimed_days = 0
    has_today = bool(init.get("isSigIn"))
    if fallback_has_today is True and not has_today:
        has_today = True
        claimed_days = max(claimed_days, 1) if claimed_days == 0 else claimed_days

    days_out: list[dict[str, Any]] = []
    for idx, item in enumerate(configs):
        # id 是上游全局自增主键，不是本月第 N 天；格子序用数组下标
        day = idx + 1
        days_out.append(
            {
                "day": day,
                "claimed": day <= claimed_days,
                "awards": _config_awards(item),
            }
        )

    return {
        "claimed_days": claimed_days,
        "total_days": len(days_out),
        "has_today_claim": has_today,
        "progress_reliable": True,
        "days": days_out,
    }
