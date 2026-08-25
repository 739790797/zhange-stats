"""米游社游戏福利签到日历解析（自然月 awards + 已签次数）。"""

from __future__ import annotations

from typing import Any

from app.services.checkin_common import award_item


def award_from_mihoyo_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or row.get("goods_name") or "").strip()
    raw_cnt = row.get("cnt")
    if not name and isinstance(raw_cnt, str) and raw_cnt.strip():
        name = raw_cnt.strip()
    if not name:
        return None
    num = row.get("count")
    if num is None and not isinstance(raw_cnt, str):
        num = raw_cnt
    try:
        count = int(num) if num is not None else 1
    except (TypeError, ValueError):
        count = 1
    icon = str(
        row.get("icon") or row.get("icon_url") or row.get("img") or ""
    ).strip() or None
    rid = row.get("id") or row.get("goods_id")
    return award_item(
        name=name,
        count=count,
        resource_id=rid,
        resource_type=row.get("type"),
        icon_url=icon,
    )


def select_today_awards(
    awards: list[Any],
    *,
    signed: bool,
    total_sign_day: int,
    today_index: int | None = None,
) -> list[dict[str, Any]]:
    """从月奖励列表取出「今日」一条；短列表视为已是今日奖励。"""
    parsed: list[dict[str, Any]] = []
    for row in awards:
        item = award_from_mihoyo_row(row)
        if item:
            parsed.append(item)
    if not parsed:
        return []
    if len(parsed) <= 2:
        return parsed
    idx = today_index
    if idx is None:
        idx = (total_sign_day - 1) if signed else total_sign_day
    if 0 <= idx < len(parsed):
        return [parsed[idx]]
    return []


def _today_index(info: dict[str, Any]) -> int | None:
    raw = info.get("today")
    if isinstance(raw, int):
        return raw - 1 if raw > 0 else None
    text = str(raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        day = int(text)
        return day - 1 if day > 0 else None
    if "-" in text:
        tail = text.rsplit("-", 1)[-1]
        if tail.isdigit():
            day = int(tail)
            return day - 1 if day > 0 else None
    return None


def parse_mihoyo_attendance_calendar(
    raw: dict[str, Any],
    *,
    fallback_has_today: bool | None = None,
) -> dict[str, Any]:
    """从落库 raw（info + home）解析本月签到日历。

    返回:
      claimed_days, total_days, days[{day, claimed, awards}],
      has_today_claim, progress_reliable
    """
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    home = raw.get("home") if isinstance(raw.get("home"), dict) else {}
    awards_raw = home.get("awards")
    if not isinstance(awards_raw, list) or not awards_raw:
        awards_raw = info.get("awards") if isinstance(info.get("awards"), list) else []

    try:
        claimed_days = max(0, int(info.get("total_sign_day") or 0))
    except (TypeError, ValueError):
        claimed_days = 0
    has_today = bool(info.get("is_sign") or info.get("is_signed"))
    if fallback_has_today is True and not has_today:
        has_today = True
        claimed_days = max(claimed_days, 1) if claimed_days == 0 else claimed_days

    try:
        missed = int(info.get("sign_cnt_missed") or 0)
    except (TypeError, ValueError):
        missed = 0

    days_out: list[dict[str, Any]] = []
    for idx, row in enumerate(awards_raw):
        item = award_from_mihoyo_row(row)
        days_out.append(
            {
                "day": idx + 1,
                "claimed": idx < claimed_days,
                "awards": [item] if item else [],
            }
        )

    return {
        "claimed_days": claimed_days,
        "total_days": len(days_out),
        "has_today_claim": has_today,
        "progress_reliable": missed <= 0,
        "days": days_out,
        "today_index": _today_index(info),
    }
