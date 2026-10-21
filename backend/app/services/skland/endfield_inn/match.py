"""需求子句：词缀、菜系、食材同时成立；品阶 _1/_2 合成一条「或」。"""

from __future__ import annotations

import re
from typing import Any

_TIER = re.compile(r"^(.*)_([12])$")


def _stem(ingredient: str) -> str:
    matched = _TIER.match(ingredient)
    return matched.group(1) if matched else ingredient


def clauses_for(requirement: dict[str, Any], describes: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple, dict[str, Any]] = {}
    order: list[tuple] = []
    for describe_id in requirement.get("describe") or []:
        raw = describes.get(describe_id)
        if not isinstance(raw, dict):
            continue
        affix = str(raw.get("affix") or "")
        category = str(raw.get("category") or "")
        ingredient = str(raw.get("ingredient") or "")
        positive = bool(raw.get("boolFlag"))
        key = (affix, category, positive, _stem(ingredient) if ingredient else "")
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "affix": affix,
                "category": category,
                "positive": positive,
                "ingredients": [],
            }
            grouped[key] = bucket
            order.append(key)
        if ingredient and ingredient not in bucket["ingredients"]:
            bucket["ingredients"].append(ingredient)
    return [grouped[key] for key in order]


def _holds(item: dict[str, Any], clause: dict[str, Any]) -> bool:
    ok = True
    affix = clause["affix"]
    category = clause["category"]
    ingredients = clause["ingredients"]
    if affix:
        ok = ok and affix in (item.get("affix") or [])
    if category:
        ok = ok and item.get("category") == category
    if ingredients:
        have = set(item.get("ingredients") or [])
        ok = ok and any(name in have for name in ingredients)
    if not affix and not category and not ingredients:
        ok = False
    return ok if clause["positive"] else not ok


def matches_perfect(
    item: dict[str, Any],
    clauses: list[dict[str, Any]],
    *,
    requirement_flag: bool = True,
) -> bool:
    """评估要求表的组合符：true 为全部子句，false 为任一子句。"""
    if not clauses:
        return False
    checks = (_holds(item, clause) for clause in clauses)
    return all(checks) if requirement_flag else any(checks)
