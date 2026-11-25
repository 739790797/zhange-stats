"""Project basic-game skill and module reference data for Stronghold's chess roster."""

import math
import re

from app.services.skland.stronghold_source import _description, _icon, _key, _label, _number, _obj

_PARAM = re.compile(r"\{([\w@.\-]+)(?::(0(?:\.0{1,3})?%?))?\}")
_EQUIP_ICONS = "https://web.hycdn.cn/arknights/game/assets/uniequip"
_ATTRIBUTES = {
    "atk": "攻击力",
    "max_hp": "生命上限",
    "def": "防御力",
    "attack_speed": "攻击速度",
    "cost": "部署费用",
    "magic_resistance": "法术抗性",
    "respawn_time": "再部署时间",
    "block_cnt": "阻挡数",
}


def list_values(raw: object) -> list:
    return raw if isinstance(raw, list) else []


def _blackboard(raw: object) -> dict:
    return {key: item for item in map(_obj, list_values(raw)) if isinstance(key := item.get("key"), str)}


def _value(raw: object) -> float | None:
    if type(raw) in (int, float) and math.isfinite(raw):
        return raw
    return None


def _effect(raw: object, blackboard: object) -> str | None:
    desc = _description(raw)
    if not desc:
        return None
    values = _blackboard(blackboard)

    def expand(match: re.Match) -> str:
        key, spec = match.groups()
        entry = values.get(key, {})
        value = _value(entry.get("value"))
        if value is None:
            return _label(entry.get("valueStr")) or "…"
        if not spec:
            return format(value, "g")
        if spec.endswith("%"):
            value *= 100
        decimals = len(spec.split(".", 1)[1].rstrip("%")) if "." in spec else 0
        return f"{value:.{decimals}f}{'%' if spec.endswith('%') else ''}"

    return _PARAM.sub(expand, desc)


def skill_reference(item: dict) -> dict:
    levels = {}
    name = None
    for i, level in enumerate(list_values(item.get("levels"))[:10], 1):
        level = _obj(level)
        name = name or _label(level.get("name"))
        if text := _effect(level.get("description"), level.get("blackboard")):
            levels[str(i)] = text
    # No guessed CDN URL: the frontend uses the existing resource-repo skill icon.
    return {"name": name, "levels": levels} if name else {}


def _module_effect(phase: dict) -> str | None:
    lines = []
    for attr, entry in _blackboard(phase.get("attributeBlackboard")).items():
        label = _ATTRIBUTES.get(attr)
        value = _value(entry.get("value"))
        if label and value:
            lines.append(f"{label} {value:+g}")
    sentences = [" · ".join(lines)] if lines else []
    for part in list_values(phase.get("parts")):
        for kind, attrs in (
            ("overrideTraitDataBundle", ("overrideDescripton", "additionalDescription")),
            ("addOrOverrideTalentDataBundle", ("upgradeDescription", "description")),
        ):
            candidates = list_values(_obj(_obj(part).get(kind)).get("candidates"))
            candidate = next((item for item in map(_obj, candidates) if item.get("requiredPotentialRank", 0) == 0), {})
            if kind == "addOrOverrideTalentDataBundle":
                raw = next((candidate[attr] for attr in attrs if candidate.get(attr)), None)
                descriptions = [raw]
            else:
                descriptions = [candidate.get(attr) for attr in attrs]
            for raw in descriptions:
                if (text := _effect(raw, candidate.get("blackboard"))) and text not in sentences:
                    sentences.append(text)
    return _description("\n".join(sentences))


def module_reference(item: dict, battle: dict) -> dict:
    if not (name := _label(item.get("uniEquipName"))):
        return {}
    icon = _key(item.get("uniEquipIcon"))
    levels = {}
    for phase in map(_obj, list_values(battle.get("phases"))):
        if (level := _number(phase.get("equipLevel"))) and (text := _module_effect(phase)):
            levels[str(level)] = text
    return {"name": name, "icon_url": _icon(f"{_EQUIP_ICONS}/{icon}.png") if icon else None, "levels": levels}
