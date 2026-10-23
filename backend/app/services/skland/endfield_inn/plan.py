"""准备阶段：按主题凑菜单、排厨师，并估算 5 星要做的事。"""

from __future__ import annotations

import math
import re
from typing import Any

from app.services.skland.endfield_inn.load import (
    AFFIX_CN,
    CATEGORY_CN,
    InnInvalidInput,
    InnTopicNotFound,
    load_tables,
    resolve_text,
)
from app.services.skland.endfield_inn.match import clauses_for, matches_perfect

_SELL = 16004
_RARE = 16005
_GOURMAND = 16007
_REVENUE = 16009
_BLAZE = 16010
_STREAK = 16012
_NO_OBJECTIVE = 2147483647
_RICH_IMAGE_TAG = re.compile(r'\s*<image="[^"]+"(?:\s+[^>]*)?>\s*')
_IMAGE_TAG = re.compile(r'<image="([^"]+)"(?:\s+[^>]*)?>')
_INN_TYPE_ICON = re.compile(r"^Inn/Type/(icon_inn_[a-z0-9_]+)$", re.IGNORECASE)


def _plain_objective_text(value: str) -> str:
    """Remove unsupported game rich-text image markup from user-facing text."""
    return _RICH_IMAGE_TAG.sub("", value).strip()


def _objective_parts(value: str) -> list[dict[str, str]]:
    """Keep supported Inn category icons as safe, ordered presentation parts."""
    parts: list[dict[str, str]] = []
    cursor = 0
    for match in _IMAGE_TAG.finditer(value):
        text = value[cursor : match.start()]
        if text:
            parts.append({"kind": "text", "value": text})
        icon = _INN_TYPE_ICON.fullmatch(match.group(1))
        if icon:
            parts.append({"kind": "icon", "value": icon.group(1)})
        cursor = match.end()
    text = value[cursor:]
    if text:
        parts.append({"kind": "text", "value": text})
    return parts


def _level_row(tables: dict[str, Any], level: int) -> dict[str, Any]:
    row = tables["levels"].get(str(level))
    if not isinstance(row, dict):
        raise InnInvalidInput("客栈等级无效")
    return row


def _expansions_for_level(tables: dict[str, Any], level: int, expansion_ids: list[str] | None) -> list[str]:
    chosen: list[str] = []
    for expansion_id in expansion_ids or []:
        if not expansion_id or expansion_id in chosen:
            continue
        row = tables["expansions"].get(expansion_id)
        if not isinstance(row, dict):
            raise InnInvalidInput(f"未知扩建：{expansion_id}")
        unlock_level = int(row.get("unlockLevel") or 0)
        if unlock_level > level:
            raise InnInvalidInput(f"扩建 {expansion_id} 需客栈 {unlock_level} 级")
        chosen.append(expansion_id)
    selected = set(chosen)
    for expansion_id in chosen:
        row = tables["expansions"].get(expansion_id)
        prerequisite = str(row.get("prerequisiteId") or "") if isinstance(row, dict) else ""
        if prerequisite and prerequisite not in selected:
            raise InnInvalidInput(f"扩建 {expansion_id} 需先完成 {prerequisite}")
    return chosen


def _label_affix(key: str, tables: dict[str, Any]) -> str:
    row = tables["affixes"].get(key) if isinstance(tables["affixes"], dict) else None
    text = resolve_text(row.get("name") if isinstance(row, dict) else None, tables["i18n"])
    return text or AFFIX_CN.get(key) or key


def _label_category(key: str, tables: dict[str, Any]) -> str:
    row = tables["categories"].get(key) if isinstance(tables["categories"], dict) else None
    text = resolve_text(row.get("name") if isinstance(row, dict) else None, tables["i18n"])
    return text or CATEGORY_CN.get(key) or key


def _label_item(item_id: str, tables: dict[str, Any]) -> str:
    return tables["item_names"].get(item_id) or item_id


def _normalize_dish(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "category": str(row.get("category") or ""),
        "affix": [str(item) for item in row.get("affix") or []],
        "ingredients": [str(item) for item in row.get("ingredient") or []],
        "price": int(row.get("price") or 0),
        "timeCost": int(row.get("timeCost") or 0),
        "unlockLevel": int(row.get("unlockLevel") or 0),
        "unlockTopicId": str(row.get("unlockTopicId") or ""),
        "unlockTopicStarNum": int(row.get("unlockTopicStarNum") or 0),
    }


def _normalize_drink(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "category": "drink",
        "affix": [str(item) for item in row.get("affix") or []],
        "ingredients": [],
        "price": int(row.get("price") or 0),
        "timeCost": 0,
        "unlockLevel": int(row.get("unlockLevel") or 0),
        "unlockTopicId": str(row.get("unlockTopicId") or ""),
        "unlockTopicStarNum": int(row.get("unlockTopicStarNum") or 0),
    }


def _category_unlock_level(tables: dict[str, Any], category: str) -> int:
    levels = [
        int(level_id)
        for level_id, row in tables["levels"].items()
        if isinstance(row, dict) and category in {str(item) for item in row.get("usableDishType") or []}
    ]
    return min(levels, default=1)


def _dish_unlock_info(
    item: dict[str, Any],
    tables: dict[str, Any],
    level: int,
    topic_stars: dict[str, int],
) -> dict[str, Any]:
    required_level = max(
        int(item.get("unlockLevel") or 0),
        _category_unlock_level(tables, str(item.get("category") or "")),
    )
    topic_id = str(item.get("unlockTopicId") or "")
    required_stars = int(item.get("unlockTopicStarNum") or 0)
    conditions: list[str] = []
    if required_level > 1:
        conditions.append(f"客栈 {required_level} 级")
    if topic_id and required_stars > 0:
        topic = tables["topics"].get(topic_id)
        topic_name = (resolve_text(topic.get("name"), tables["i18n"]) if isinstance(topic, dict) else "") or topic_id
        conditions.append(f"「{topic_name}」主题达成 {required_stars} 星")
    stars_met = not topic_id or topic_stars.get(topic_id, 0) >= required_stars
    return {
        "unlock_level": required_level,
        "unlock_topic_id": topic_id,
        "unlock_topic_star_num": required_stars,
        "unlocked": level >= required_level and stars_met,
        "unlock_conditions": conditions,
    }


def _all_dishes(tables: dict[str, Any]) -> list[dict[str, Any]]:
    return [_normalize_dish(row) for row in tables["dishes"].values() if isinstance(row, dict)]


def _all_drinks(tables: dict[str, Any]) -> list[dict[str, Any]]:
    return [_normalize_drink(row) for row in tables["drinks"].values() if isinstance(row, dict)]


def _available_dishes(
    tables: dict[str, Any], level: int, topic_stars: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    progress = topic_stars or {}
    return [dish for dish in _all_dishes(tables) if _dish_unlock_info(dish, tables, level, progress)["unlocked"]]


def _available_drinks(
    tables: dict[str, Any], level: int, topic_stars: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    progress = topic_stars or {}
    return [drink for drink in _all_drinks(tables) if _dish_unlock_info(drink, tables, level, progress)["unlocked"]]


def _pool_for(
    requirement: dict[str, Any], dishes: list[dict[str, Any]], drinks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return drinks if int(requirement.get("foodType") or 1) == 2 else dishes


def _rank(item: dict[str, Any], hot_affix: set[str], hot_category: set[str]) -> tuple:
    affix_hit = len(set(item["affix"]) & hot_affix)
    category_hit = 1 if item["category"] in hot_category else 0
    return (-affix_hit, -category_hit, -item["price"], item["timeCost"], item["id"])


def _clause_text(clause: dict[str, Any], tables: dict[str, Any]) -> str:
    parts: list[str] = []
    if clause["category"]:
        parts.append(_label_category(clause["category"], tables))
    if clause["affix"]:
        parts.append(_label_affix(clause["affix"], tables))
    if clause["ingredients"]:
        parts.append("或".join(_label_item(item, tables) for item in clause["ingredients"]))
    body = "、".join(parts) or "无限制"
    return body if clause["positive"] else f"不要{body}"


def _requirement_text(requirement: dict[str, Any], clauses: list[dict[str, Any]], tables: dict[str, Any]) -> str:
    menu = resolve_text(requirement.get("menuDesc"), tables["i18n"])
    if menu:
        return menu
    guest = resolve_text(requirement.get("requirementText"), tables["i18n"])
    if guest:
        return guest
    separator = "，且" if bool(requirement.get("boolFlag")) else "，或"
    return separator.join(_clause_text(clause, tables) for clause in clauses)


def _dish_out(
    item: dict[str, Any],
    tables: dict[str, Any],
    unlock_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    info = unlock_info or {
        "unlock_level": max(int(item.get("unlockLevel") or 0), 1),
        "unlock_topic_id": str(item.get("unlockTopicId") or ""),
        "unlock_topic_star_num": int(item.get("unlockTopicStarNum") or 0),
        "unlocked": True,
        "unlock_conditions": [],
    }
    return {
        "id": item["id"],
        "name": _label_item(item["id"], tables),
        "category": item["category"],
        "category_name": _label_category(item["category"], tables),
        "affix_ids": item["affix"],
        "affixes": [_label_affix(key, tables) for key in item["affix"]],
        "price": item["price"],
        "cook_seconds": item["timeCost"],
        "ingredients": [_label_item(name, tables) for name in item["ingredients"]],
        **info,
    }


def _menu(
    topic: dict[str, Any],
    tables: dict[str, Any],
    dishes: list[dict[str, Any]],
    drinks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hot_affix = {str(item) for item in topic.get("hotAffix") or []}
    hot_category = {str(item) for item in topic.get("hotCategory") or []}
    pending: list[tuple[int, str, int, list[dict[str, Any]], list[dict[str, Any]]]] = []
    for index, requirement_id in enumerate(topic.get("requirementList") or []):
        requirement = tables["requirements"].get(requirement_id)
        if not isinstance(requirement, dict):
            continue
        nums = topic.get("requirementNum") or []
        need = int(nums[index]) if index < len(nums) else 0
        if need <= 0:
            continue
        clauses = clauses_for(requirement, tables["describes"])
        pool = _pool_for(requirement, dishes, drinks)
        found = [
            item for item in pool if matches_perfect(item, clauses, requirement_flag=bool(requirement.get("boolFlag")))
        ]
        found.sort(key=lambda item: _rank(item, hot_affix, hot_category))
        pending.append((len(found), str(requirement_id), need, found, clauses))
    pending.sort(key=lambda row: (row[0], row[1]))
    used: set[str] = set()
    groups: list[dict[str, Any]] = []
    for _count, requirement_id, need, found, clauses in pending:
        requirement = tables["requirements"][requirement_id]
        chosen: list[dict[str, Any]] = []
        fresh = [item for item in found if item["id"] not in used]
        for item in fresh or found:
            if len(chosen) >= need:
                break
            if any(picked["id"] == item["id"] for picked in chosen):
                continue
            chosen.append(item)
            used.add(item["id"])
        groups.append(
            {
                "requirement_id": requirement_id,
                "text": _requirement_text(requirement, clauses, tables),
                "food_type": int(requirement.get("foodType") or 1),
                "need": need,
                "dishes": [_dish_out(item, tables) for item in chosen],
                "missing": max(need - len(chosen), 0),
            }
        )
    return groups


def _skill_focus(skill: dict[str, Any]) -> tuple[str, str]:
    strings: list[str] = []
    for param in skill.get("parameters") or []:
        if isinstance(param, dict):
            strings.extend(str(item) for item in param.get("valueStringList") or [] if item)
    category = next((item for item in strings if item in CATEGORY_CN), "")
    affix = next((item for item in strings if item in AFFIX_CN), "")
    return category, affix


def _skill_value(skill: dict[str, Any]) -> float:
    for param in skill.get("parameters") or []:
        if not isinstance(param, dict):
            continue
        values = param.get("valueFloatList") or []
        for value in values:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if parsed:
                return parsed
    return 0.0


def _percent_label(value: float) -> str:
    percent = value * 100
    if math.isclose(percent, round(percent)):
        return f"{int(round(percent))}%"
    return f"{percent:g}%"


def _kitchen_count(tables: dict[str, Any], expansions: list[str]) -> int:
    kitchens = int(tables["const"].get("initKitchenNum") or 1)
    for expansion_id in expansions:
        row = tables["expansions"].get(expansion_id)
        if isinstance(row, dict):
            kitchens += max(int(row.get("addKitchenNum") or 0), 0)
    return kitchens


def _chef_slot_count(tables: dict[str, Any], level: int, expansions: list[str]) -> tuple[int, int, int]:
    kitchens = _kitchen_count(tables, expansions)
    per_kitchen = max(int(_level_row(tables, level).get("kitchenStuffNum") or 1), 1)
    extra_slots = sum(
        max(int(row.get("addKitchenCharNum") or 0), 0)
        for expansion_id in expansions
        if isinstance((row := tables["expansions"].get(expansion_id)), dict)
    )
    return kitchens, kitchens * per_kitchen + extra_slots, per_kitchen


def _chef_skill_note(skill: dict[str, Any], tables: dict[str, Any], level: int) -> tuple[str, str, str]:
    category, affix = _skill_focus(skill)
    kind = int(skill.get("skillType") or 0)
    unlock = int(skill.get("unlockLevel") or 0)
    value = _skill_value(skill)
    bonus = f" +{_percent_label(value)}" if value else ""
    locked = bool(unlock and level < unlock)
    if kind == 0 and category:
        label = f"{_label_category(category, tables)}加速{bonus}"
        tag_id = f"category:{category}"
        tag_label = _label_category(category, tables)
    elif kind == 1 and affix:
        label = f"{_label_affix(affix, tables)}小费{bonus}"
        tag_id = f"affix:{affix}"
        tag_label = _label_affix(affix, tables)
    elif kind == 2:
        label = f"珍馐出餐率{bonus}"
        tag_id = "skill:rare_rate"
        tag_label = "珍馐出餐率"
    else:
        return "", "", ""
    if locked:
        label += f"（客栈 {unlock} 级后生效）"
    return label, tag_id, tag_label


def _chefs(
    tables: dict[str, Any],
    menu: list[dict[str, Any]],
    topic: dict[str, Any],
    level: int,
    expansions: list[str],
) -> list[dict[str, Any]]:
    const = tables["const"]
    blocked = {str(item) for item in const.get("notAllowedKitchenChar") or []}
    allowed = {
        str(row.get("charId") or char_id) for char_id, row in tables["inn_chars"].items() if isinstance(row, dict)
    }
    kitchens, staff_slots, per_kitchen = _chef_slot_count(tables, level, expansions)
    regular_slots = kitchens * per_kitchen
    categories = {dish["category"] for group in menu for dish in group["dishes"]}
    hot_affix = {str(item) for item in topic.get("hotAffix") or []}
    ranked: list[tuple[int, str, list[str]]] = []
    for char_id, row in tables["char_skills"].items():
        char_id = str(char_id)
        if char_id not in allowed or char_id in blocked or not isinstance(row, dict):
            continue
        score = 0
        notes: list[str] = []
        for skill_id in row.get("list") or []:
            skill = tables["skills"].get(skill_id)
            if not isinstance(skill, dict):
                continue
            category, affix = _skill_focus(skill)
            unlock = int(skill.get("unlockLevel") or 0)
            kind = int(skill.get("skillType") or 0)
            value = _skill_value(skill)
            bonus = f" +{_percent_label(value)}" if value else ""
            locked = bool(unlock and level < unlock)
            if kind == 0 and category and category in categories:
                notes.append(f"{_label_category(category, tables)}加速{bonus}")
                if not locked:
                    score += 2
            elif kind == 1 and affix and affix in hot_affix:
                label = f"{_label_affix(affix, tables)}小费{bonus}"
                notes.append(f"{label}（客栈 {unlock} 级后生效）" if locked else label)
                if not locked:
                    score += 1
            elif kind == 2:
                label = f"稀有出餐率{bonus}"
                notes.append(f"{label}（客栈 {unlock} 级后生效）" if locked else label)
                if not locked:
                    score += 1
        if score or notes:
            ranked.append((score, str(char_id), notes))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    chefs: list[dict[str, Any]] = []
    for index, (_score, char_id, notes) in enumerate(ranked[:staff_slots]):
        if index < regular_slots:
            kitchen_index = index // per_kitchen + 1
            slot_in_kitchen = index % per_kitchen + 1
            slot_label = (
                f"{kitchen_index} 号厨房" if per_kitchen == 1 else f"{kitchen_index} 号厨房 · 人员位 {slot_in_kitchen}"
            )
        else:
            kitchen_index = None
            slot_label = f"额外厨师位 {index - regular_slots + 1}"
        chefs.append(
            {
                "char_id": char_id,
                "name": tables["char_names"].get(char_id) or char_id,
                "kitchen_index": kitchen_index,
                "slot_label": slot_label,
                "notes": notes,
            }
        )
    return chefs


def _chef_catalog(tables: dict[str, Any], level: int) -> list[dict[str, Any]]:
    blocked = {str(item) for item in tables["const"].get("notAllowedKitchenChar") or []}
    allowed = {
        str(row.get("charId") or char_id) for char_id, row in tables["inn_chars"].items() if isinstance(row, dict)
    }
    catalog: list[dict[str, Any]] = []
    for char_id in sorted(allowed - blocked):
        row = tables["char_skills"].get(char_id)
        notes: list[str] = []
        tags: dict[str, str] = {}
        if isinstance(row, dict):
            for skill_id in row.get("list") or []:
                skill = tables["skills"].get(skill_id)
                if not isinstance(skill, dict):
                    continue
                note, tag_id, tag_label = _chef_skill_note(skill, tables, level)
                if note:
                    notes.append(note)
                if tag_id:
                    tags[tag_id] = tag_label
        catalog.append(
            {
                "char_id": char_id,
                "name": tables["char_names"].get(char_id) or char_id,
                "tags": [{"id": tag_id, "label": label} for tag_id, label in sorted(tags.items())],
                "notes": notes,
            }
        )
    return catalog


def _objective_requirement(topic: dict[str, Any]) -> str:
    for param in topic.get("objectiveParameters") or []:
        if not isinstance(param, dict):
            continue
        values = param.get("valueStringList") or []
        if values:
            return str(values[0])
    return ""


def _objective_guest_result(topic: dict[str, Any]) -> str:
    for param in topic.get("objectiveParameters") or []:
        if not isinstance(param, dict):
            continue
        for value in param.get("valueStringList") or []:
            value = str(value)
            if "ServeSpecialGuestResultType" in value:
                return value.rsplit("_", 1)[-1]
    return ""


def _play_time(topic: dict[str, Any], const: dict[str, Any]) -> int:
    override = int(topic.get("overridePlayTime") or 0)
    return override or int(const.get("playTime") or 300)


def _star(
    topic: dict[str, Any],
    tables: dict[str, Any],
    menu: list[dict[str, Any]],
    dishes: list[dict[str, Any]],
    drinks: list[dict[str, Any]],
    level: int,
    kitchens: int,
) -> dict[str, Any]:
    const = tables["const"]
    level_row = _level_row(tables, level)
    scores = [int(item) for item in topic.get("starRequiredScore") or []]
    kpi = float(topic.get("topicKPIScoreLimit") or 0)
    profit = float(topic.get("topicProfitScoreLimit") or 0)
    private = int(topic.get("topicType") or 1) == 2
    kind = int(topic.get("objectiveConditionType") or 0)
    target = int(topic.get("oProgressToCompare") or 0)
    objective_source = resolve_text(topic.get("objectiveDesc"), tables["i18n"])
    objective_text = _plain_objective_text(objective_source)
    objective_parts = _objective_parts(objective_source)
    if private or kind == _NO_OBJECTIVE:
        objective = "没有星级奖励" if private else objective_text
        return {
            "private_chef": private,
            "star_scores": scores,
            "kpi_cap": kpi,
            "profit_cap": profit,
            "needs_objective": False,
            "objective": objective,
            "objective_parts": _objective_parts(objective) if private else objective_parts,
            "estimate": "私厨不按主题星级结算。" if private else "",
        }
    needs = bool(scores) and kpi + profit < scores[-1]
    play = _play_time(topic, const)
    estimate = _estimate(
        kind,
        target,
        topic,
        tables,
        menu,
        dishes,
        drinks,
        level_row,
        const,
        kitchens,
        play,
    )
    if not objective_text:
        objective_text = estimate
        objective_parts = _objective_parts(estimate)
    return {
        "private_chef": False,
        "star_scores": scores,
        "kpi_cap": kpi,
        "profit_cap": profit,
        "needs_objective": needs,
        "objective": objective_text,
        "objective_parts": objective_parts,
        "estimate": estimate,
    }


def _estimate(
    kind: int,
    target: int,
    topic: dict[str, Any],
    tables: dict[str, Any],
    menu: list[dict[str, Any]],
    dishes: list[dict[str, Any]],
    drinks: list[dict[str, Any]],
    level_row: dict[str, Any],
    const: dict[str, Any],
    kitchens: int,
    play: int,
) -> str:
    if kind == _SELL:
        return _estimate_sell(target, topic, tables, dishes, drinks, kitchens, play)
    if kind == _RARE:
        return f"售出带稀有标签的菜 {target} 份。稀有是出餐时随机加上的，开张前无法排进固定菜单。"
    if kind == _GOURMAND:
        limit = int(topic.get("overrideSpecialGuestLimit") or 0) or int(level_row.get("specialGuestLimit") or 0)
        if limit <= 0:
            return f"需要接待老饕 {target} 次。该客栈等级没有老饕。"
        sessions = math.ceil(target / limit) if target else 0
        result_type = _objective_guest_result(topic)
        result_label = "完美接待" if result_type.lower() == "perfect" else "普通接待即可"
        return f"需要老饕{result_label} {target} 次。本局最多 {limit} 位，大约 {sessions} 局。"
    if kind == _REVENUE:
        prices = [dish["price"] for group in menu for dish in group["dishes"]]
        price = max(prices) if prices else 0
        tip = float(level_row.get("tipRate") or 0)
        unit = price * (1 + tip)
        orders = math.ceil(target / unit) if unit else 0
        return f"本局营收达到 {target}。按菜单最高标价 {price}、小费 {tip:.0%}，至少成功售出 {orders} 单。"
    if kind == _BLAZE:
        unlock = int(const.get("rushUnlockLevel") or 3)
        return f"发动全力火候 {target} 次。客栈 {unlock} 级解锁。气槽如何攒满，数据里没有完整公式。"
    if kind == _STREAK:
        order = int(topic.get("overrideOrderTime") or 0) or int(const.get("orderTime") or 0)
        eat = int(topic.get("overrideFoodEatingTime") or 0) or int(const.get("foodEatingTime") or 0)
        leave = int(const.get("guestLeaveTime") or 0)
        cycle = order + eat + leave
        desks = int(level_row.get("deskNum") or 0)
        capacity = int(desks * play / cycle) if cycle else 0
        return (
            f"连续成功接待 {target} 位。"
            f"按 {desks} 张桌子、一轮约 {cycle} 秒、本局 {play} 秒，大约能接待 {capacity} 位。"
        )
    return f"完成主题目标 {target}。"


def _estimate_sell(
    target: int,
    topic: dict[str, Any],
    tables: dict[str, Any],
    dishes: list[dict[str, Any]],
    drinks: list[dict[str, Any]],
    kitchens: int,
    play: int,
) -> str:
    requirement_id = _objective_requirement(topic)
    requirement = tables["requirements"].get(requirement_id)
    clauses = clauses_for(requirement, tables["describes"]) if isinstance(requirement, dict) else []
    pool = _pool_for(requirement, dishes, drinks) if isinstance(requirement, dict) else dishes
    focused = [
        dish["timeCost"]
        for dish in pool
        if dish["timeCost"] > 0
        and matches_perfect(
            dish,
            clauses,
            requirement_flag=bool(requirement.get("boolFlag")) if isinstance(requirement, dict) else True,
        )
    ]
    cook = min(focused) if focused else 0
    if not isinstance(requirement, dict):
        return f"售出符合目标的菜 {target} 份。上游没有提供目标条件，无法估算产能。"
    if not cook:
        return f"售出符合目标的菜 {target} 份。当前等级没有可确认符合目标的菜谱，无法估算产能。"
    capacity = kitchens * (play // cook) if cook else 0
    gap = "一局可能不够。" if capacity < target else "一局的后厨时间盖得住。"
    return f"售出符合目标的菜 {target} 份。按最快符合条件菜谱 {cook} 秒、后厨 {kitchens} 口、本局 {play} 秒，约可制作 {capacity} 份。{gap}"


def _jsspsi_bonus_tiers(tables: dict[str, Any]) -> list[dict[str, Any]]:
    const = tables["const"]
    fields = (
        "jsspsiFirstStageSkillParam",
        "jsspsiSecondStageSkillParam",
        "jsspsiThirdStageSkillParam",
    )
    tiers: list[dict[str, Any]] = []
    for tier, field in enumerate(fields, start=1):
        raw = const.get(field)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            tiers.append({"tier": tier, "rare_rate_bonus": round(value, 6)})
    return tiers


def list_topics(*, root=None) -> dict[str, Any]:
    tables = load_tables(root=root)
    topics = []
    for topic_id, row in tables["topics"].items():
        if not isinstance(row, dict):
            continue
        topics.append(
            {
                "id": str(topic_id),
                "name": resolve_text(row.get("name"), tables["i18n"]) or str(topic_id),
                "unlock_level": int(row.get("unlockLevel") or 1),
                "private_chef": int(row.get("topicType") or 1) == 2,
                "sort_id": int(row.get("sortId") or 0),
            }
        )
    topics.sort(key=lambda item: (item["sort_id"], item["id"]))
    for item in topics:
        item.pop("sort_id", None)
    expansions = []
    for expansion_id, row in tables["expansions"].items():
        if not isinstance(row, dict):
            continue
        expansions.append(
            {
                "id": str(expansion_id),
                "name": resolve_text(row.get("name"), tables["i18n"]) or str(expansion_id),
                "unlock_level": int(row.get("unlockLevel") or 1),
                "cost": int(row.get("cost") or 0),
                "add_kitchen_num": int(row.get("addKitchenNum") or 0),
                "add_kitchen_char_num": int(row.get("addKitchenCharNum") or 0),
                "prerequisite_id": str(row.get("prerequisiteId") or ""),
                "sort_id": int(row.get("sortId") or 0),
            }
        )
    expansions.sort(key=lambda item: (item["sort_id"], item["id"]))
    for item in expansions:
        item.pop("sort_id", None)
    return {
        "topics": topics,
        "expansions": expansions,
        "jsspsi_bonus_tiers": _jsspsi_bonus_tiers(tables),
    }


def build_inn_query(
    *,
    level: int,
    expansions: list[str] | None = None,
    topic_id: str | None = None,
    topic_stars: dict[str, int] | None = None,
    jsspsi_bonus_tier: int = 1,
    root=None,
) -> dict[str, Any]:
    if level < 1 or level > 4:
        raise InnInvalidInput("客栈等级无效")
    tables = load_tables(root=root)
    progress: dict[str, int] = {}
    for progress_topic_id, raw_stars in (topic_stars or {}).items():
        if progress_topic_id not in tables["topics"]:
            raise InnInvalidInput(f"未知主题星级：{progress_topic_id}")
        if isinstance(raw_stars, bool):
            raise InnInvalidInput("主题星级须为 0 至 5 星")
        try:
            stars = int(raw_stars)
        except (TypeError, ValueError) as exc:
            raise InnInvalidInput("主题星级须为 0 至 5 星") from exc
        if stars < 0 or stars > 5 or stars != raw_stars:
            raise InnInvalidInput("主题星级须为 0 至 5 星")
        progress[str(progress_topic_id)] = stars

    topic = None
    if topic_id:
        topic = tables["topics"].get(topic_id)
        if not isinstance(topic, dict):
            raise InnTopicNotFound("没有这个主题")
        topic_unlock = int(topic.get("unlockLevel") or 0)
        if topic_unlock > level:
            raise InnInvalidInput(f"该主题需客栈 {topic_unlock} 级")

    chosen = _expansions_for_level(tables, level, expansions)
    bonus_tiers = _jsspsi_bonus_tiers(tables)
    bonus_by_tier = {item["tier"]: item["rare_rate_bonus"] for item in bonus_tiers}
    if jsspsi_bonus_tier not in bonus_by_tier:
        raise InnInvalidInput("祀经营加成档位无效")

    all_dishes = _all_dishes(tables)
    all_drinks = _all_drinks(tables)
    dish_catalog = [_dish_out(item, tables, _dish_unlock_info(item, tables, level, progress)) for item in all_dishes]
    drink_catalog = [_dish_out(item, tables, _dish_unlock_info(item, tables, level, progress)) for item in all_drinks]
    dish_catalog.sort(key=lambda item: (item["category"], item["unlock_level"], item["name"], item["id"]))
    drink_catalog.sort(key=lambda item: (item["unlock_level"], item["name"], item["id"]))
    kitchens, chef_slots, _per_kitchen = _chef_slot_count(tables, level, chosen)

    recommendations = None
    if topic is not None and topic_id is not None:
        dishes = _available_dishes(tables, level, progress)
        drinks = _available_drinks(tables, level, progress)
        menu = _menu(topic, tables, dishes, drinks)
        chefs = _chefs(tables, menu, topic, level, chosen)
        recommendations = {
            "topic_id": topic_id,
            "topic_name": resolve_text(topic.get("name"), tables["i18n"]) or topic_id,
            "menu": menu,
            "chefs": chefs,
            "star": _star(topic, tables, menu, dishes, drinks, level, kitchens),
        }

    return {
        "level": level,
        "topic_id": topic_id,
        "kitchen_count": kitchens,
        "chef_slot_count": chef_slots,
        "jsspsi_bonus_tier": jsspsi_bonus_tier,
        "jsspsi_rare_rate_bonus": bonus_by_tier[jsspsi_bonus_tier],
        "dishes": dish_catalog,
        "drinks": drink_catalog,
        "chef_catalog": _chef_catalog(tables, level),
        "recommendations": recommendations,
    }


def build_plan(topic_id: str, level: int, expansions: list[str] | None = None, *, root=None) -> dict[str, Any]:
    if level < 1 or level > 4:
        raise InnInvalidInput("客栈等级无效")
    tables = load_tables(root=root)
    topic = tables["topics"].get(topic_id)
    if not isinstance(topic, dict):
        raise InnTopicNotFound("没有这个主题")
    topic_unlock = int(topic.get("unlockLevel") or 0)
    if topic_unlock > level:
        raise InnInvalidInput(f"该主题需客栈 {topic_unlock} 级")
    chosen = _expansions_for_level(tables, level, expansions)
    dishes = _available_dishes(tables, level)
    drinks = _available_drinks(tables, level)
    menu = _menu(topic, tables, dishes, drinks)
    chefs = _chefs(tables, menu, topic, level, chosen)
    kitchens = _kitchen_count(tables, chosen)
    return {
        "topic_id": topic_id,
        "topic_name": resolve_text(topic.get("name"), tables["i18n"]) or topic_id,
        "level": level,
        "menu": menu,
        "chefs": chefs,
        "star": _star(topic, tables, menu, dishes, drinks, level, kitchens),
    }
