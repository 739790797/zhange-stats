"""森空岛签到奖励解析（纯函数，无 client 依赖）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# 与前端 arknights/constants.ts GAME_RES 同源
ARKNIGHTS_ITEM_ICON_BASE = (
    "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/item"
)


@lru_cache(maxsize=1)
def _item_icon_ids() -> dict[str, str]:
    """itemId → iconId（ArknightsGameResource/item/{iconId}.png）。"""
    path = (
        Path(__file__).resolve().parent.parent
        / "resources"
        / "arknights_item_icon_ids.json"
    )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if v}


def resolve_arknights_icon_key(
    *,
    resource_id: Any = None,
    resource_type: Any = None,
) -> str | None:
    """优先用 itemId 查 iconId；否则回退 Skland type（合成玉等 type==iconId）。"""
    rid = str(resource_id).strip() if resource_id is not None else ""
    if rid:
        icon = _item_icon_ids().get(rid)
        if icon:
            return icon
    rtype = str(resource_type).strip() if resource_type is not None else ""
    return rtype or None


def arknights_item_icon_url(
    resource_type: str | None = None,
    *,
    resource_id: Any = None,
) -> str | None:
    """按 iconId（或兼容旧调用的 type）拼物品图标 URL。"""
    key = resolve_arknights_icon_key(
        resource_id=resource_id, resource_type=resource_type
    )
    if not key or "/" in key or "\\" in key or ".." in key:
        return None
    return f"{ARKNIGHTS_ITEM_ICON_BASE}/{key}.png"


def award_dict(
    *,
    name: str,
    count: int = 1,
    resource_id: Any = None,
    resource_type: Any = None,
    with_icon: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {"name": name, "count": int(count)}
    if resource_id is not None and str(resource_id).strip():
        item["resource_id"] = str(resource_id).strip()
    rtype = str(resource_type).strip() if resource_type is not None else ""
    if rtype:
        item["resource_type"] = rtype
    if with_icon:
        icon = arknights_item_icon_url(rtype or None, resource_id=resource_id)
        if icon:
            item["icon_url"] = icon
    return item


def format_award_items(
    awards: list[Any], *, with_icons: bool = False
) -> tuple[str | None, list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    parts: list[str] = []
    for a in awards:
        if not isinstance(a, dict):
            continue
        res = a.get("resource") or {}
        if not isinstance(res, dict):
            res = {}
        name = str(res.get("name") or a.get("name") or "奖励").strip() or "奖励"
        try:
            count = int(a.get("count") or res.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        resource_id = res.get("id") or a.get("id")
        resource_type = res.get("type") or a.get("type")
        item = award_dict(
            name=name,
            count=count,
            resource_id=resource_id,
            resource_type=resource_type,
            with_icon=with_icons,
        )
        items.append(item)
        parts.append(f"{name}x{count}")
    if not parts:
        return None, []
    return "、".join(parts), items


def arknights_awards_from_sign_resp(
    resp: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    awards = (resp.get("data") or {}).get("awards") or []
    if not isinstance(awards, list):
        return None, []
    return format_award_items(awards, with_icons=True)


def endfield_awards_from_sign_resp(
    resp: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    data = resp.get("data") or {}
    award_ids = data.get("awardIds") or []
    resource_map = data.get("resourceInfoMap") or {}
    if not award_ids:
        awards = data.get("awards") or []
        if isinstance(awards, list):
            return format_award_items(awards, with_icons=False)
        return None, []
    items: list[dict[str, Any]] = []
    parts: list[str] = []
    for award in award_ids:
        award_id = award.get("id") if isinstance(award, dict) else award
        if award_id is None:
            continue
        key = str(award_id)
        res = resource_map.get(key) or resource_map.get(award_id)
        if not isinstance(res, dict):
            continue
        name = str(res.get("name") or "奖励").strip() or "奖励"
        try:
            count = int(res.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        items.append(
            award_dict(
                name=name,
                count=count,
                resource_id=award_id,
                resource_type=res.get("type"),
                with_icon=False,
            )
        )
        parts.append(f"{name}x{count}")
    if not parts:
        return None, []
    return "、".join(parts), items


def ts_is_beijing_day(ts: Any, day) -> bool:
    try:
        value = int(ts)
    except (TypeError, ValueError):
        return False
    if value > 10_000_000_000:
        value //= 1000
    from datetime import datetime

    from app.core.timeutil import BEIJING

    return datetime.fromtimestamp(value, tz=BEIJING).date() == day


def award_from_resource(
    resource_map: dict[str, Any],
    resource_id: Any,
    count: Any = 1,
    *,
    with_icon: bool = False,
) -> dict[str, Any] | None:
    if resource_id is None:
        return None
    res = resource_map.get(str(resource_id))
    if res is None and not isinstance(resource_id, str):
        res = resource_map.get(resource_id)
    if not isinstance(res, dict):
        return None
    name = str(res.get("name") or "奖励").strip() or "奖励"
    raw_count = count if count is not None else res.get("count")
    try:
        qty = int(raw_count) if raw_count is not None else 1
    except (TypeError, ValueError):
        qty = 1
    return award_dict(
        name=name,
        count=qty,
        resource_id=resource_id,
        resource_type=res.get("type"),
        with_icon=with_icon,
    )


def awards_from_claim_records(
    resp: dict[str, Any], *, day, with_icons: bool = False
) -> tuple[str | None, list[dict[str, Any]]]:
    """从领取记录中按北京自然日提取奖励。"""
    if resp.get("code") != 0:
        return None, []
    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return None, []

    resource_map = data.get("resourceInfoMap") or {}
    if not isinstance(resource_map, dict):
        resource_map = {}

    records = data.get("records") or []
    if not isinstance(records, list):
        return None, []

    award_items: list[dict[str, Any]] = []
    parts: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not ts_is_beijing_day(rec.get("ts"), day):
            continue
        if isinstance(rec.get("awards"), list):
            nested_text, nested_items = format_award_items(
                rec["awards"], with_icons=with_icons
            )
            if nested_text:
                parts.append(nested_text)
                award_items.extend(nested_items)
            continue
        rid = rec.get("awardId") or rec.get("resourceId") or rec.get("id")
        parsed = award_from_resource(
            resource_map, rid, rec.get("count"), with_icon=with_icons
        )
        if parsed is None and rid is not None:
            name = str(rec.get("name") or "奖励").strip() or "奖励"
            try:
                qty = int(rec.get("count") or 1)
            except (TypeError, ValueError):
                qty = 1
            rtype = rec.get("type") or rec.get("resourceType")
            parsed = award_dict(
                name=name,
                count=qty,
                resource_id=rid,
                resource_type=rtype,
                with_icon=with_icons,
            )
            if name == "奖励" and not rtype and not resource_map:
                parsed = None
        if parsed:
            award_items.append(parsed)
            parts.append(f"{parsed['name']}x{parsed['count']}")
    if not parts:
        return None, []
    return "、".join(parts), award_items


def has_claim_today(resp: dict[str, Any], *, day) -> bool:
    if resp.get("code") != 0:
        return False
    data = resp.get("data") or {}
    if not isinstance(data, dict):
        return False
    records = data.get("records") or []
    if not isinstance(records, list):
        return False
    return any(
        isinstance(rec, dict) and ts_is_beijing_day(rec.get("ts"), day)
        for rec in records
    )
