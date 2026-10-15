"""把 Wiki 的 Lua 数据收成图鉴条目。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from app.services.ror2.schemas import (
    Ror2ArtifactOut,
    Ror2ChallengeOut,
    Ror2DroneOut,
    Ror2EnvironmentOut,
    Ror2InteractableOut,
    Ror2ItemOut,
    Ror2MonsterOut,
    Ror2StatOut,
    Ror2SurvivorOut,
)
from app.services.ror2.lua_data import parse_lua_module
from app.services.ror2.wikitext import plain_wikitext

WIKI_ORIGIN = "https://riskofrain2.wiki.gg"

_RARITY_ORDER = (
    "Common",
    "Uncommon",
    "Legendary",
    "Boss",
    "Lunar",
    "Void",
    "Meal",
    "Hallowed",
    "Hex",
    "Page",
    "Untiered",
    "Equipment",
    "Lunar Equipment",
    "Elite Equipment",
)

_ENTRY_FIELDS = ("Rarity", "Desc", "Quote", "Description", "BaseHealth", "Name")


class Ror2WikiError(Exception):
    """Wiki 模块拉不下来，或正文解析不出条目。"""


_URL_SAFE = "()!'*,-._~"


def wiki_page_url(name: str) -> str:
    title, sep, fragment = name.partition("#")
    encoded = quote(title.replace(" ", "_"), safe=_URL_SAFE)
    url = f"{WIKI_ORIGIN}/wiki/{encoded}"
    if not sep:
        return url
    return f"{url}#{quote(fragment.replace(' ', '_'), safe=_URL_SAFE)}"


def wiki_file_url(filename: str) -> str:
    # Special:FilePath 先回一段 text/html 的 301。Chrome 会按跨源图片规则把它拦掉，图标出不来。
    # wiki.gg 的 /images/ 直接是 image/png，空格要换成下划线。
    title = filename.replace(" ", "_")
    return f"{WIKI_ORIGIN}/images/{quote(title, safe=_URL_SAFE)}"


def items_from_module(src: str, *, default_rarity: str = "") -> list[Ror2ItemOut]:
    table = _require_table(src, "items", "Items", "equipment", "Equipment")
    rows = [_item_from_entry(name, entry, default_rarity=default_rarity) for name, entry in _module_entries(table)]
    rows.sort(key=_item_sort)
    return rows


def survivors_from_module(src: str) -> list[Ror2SurvivorOut]:
    table = _require_table(src, "Survivors", "survivors", "survivor")
    rows = [_survivor_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: row.name.casefold())
    return rows


def monsters_from_module(src: str) -> list[Ror2MonsterOut]:
    table = _require_table(src, "Monsters", "monsters")
    rows = [_monster_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: (row.kind.casefold(), row.name.casefold()))
    return rows


def drones_from_module(src: str) -> list[Ror2DroneOut]:
    table = _require_table(src, "Drones", "drones")
    rows = [_drone_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: (row.kind.casefold(), row.name.casefold()))
    return rows


def environments_from_module(src: str) -> list[Ror2EnvironmentOut]:
    table = _require_table(src, "Environments", "environments")
    rows = [_environment_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: (row.stage.casefold(), row.name.casefold()))
    return rows


def challenges_from_module(src: str) -> list[Ror2ChallengeOut]:
    table = _require_table(src, "challenges", "Challenges")
    rows = [_challenge_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: (row.kind.casefold(), row.name.casefold()))
    return rows


def interactables_from_module(src: str) -> list[Ror2InteractableOut]:
    table = _require_table(src, "interactables", "Interactables")
    rows = [_interactable_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: (row.category.casefold(), row.name.casefold()))
    return rows


def artifacts_from_module(src: str) -> list[Ror2ArtifactOut]:
    table = _require_table(src, "artifact", "artifacts", "Artifacts")
    rows = [_artifact_from_entry(name, entry) for name, entry in _module_entries(table)]
    rows.sort(key=lambda row: row.name.casefold())
    return rows


def _require_table(src: str, *names: str) -> dict[Any, Any] | list[Any]:
    try:
        module = parse_lua_module(src)
    except Exception as exc:
        raise Ror2WikiError(f"模块解析失败：{exc}") from exc
    table = _named_table(module, *names)
    if not table:
        keys = _dict_keys(module)
        returned = module.get("return")
        ret_keys = _dict_keys(returned) if isinstance(returned, dict) else []
        raise Ror2WikiError(f"没有条目表，顶层键 {keys}，返回键 {ret_keys}")
    return table


def _named_table(module: dict[str, Any], *names: str) -> dict[Any, Any] | list[Any]:
    scopes: list[dict[str, Any]] = []
    returned = module.get("return")
    if isinstance(returned, dict):
        scopes.append(returned)
    scopes.append(module)
    for scope in scopes:
        for name in names:
            found = scope.get(name)
            if isinstance(found, dict) and _looks_like_entries(found):
                return found
            if isinstance(found, list) and _looks_like_entry_list(found):
                return found
    return {}


def _looks_like_entries(table: dict[Any, Any]) -> bool:
    for key, value in table.items():
        if isinstance(key, str) and isinstance(value, dict) and any(field in value for field in _ENTRY_FIELDS):
            return True
    return False


def _looks_like_entry_list(rows: list[Any]) -> bool:
    return any(isinstance(item, dict) and any(field in item for field in _ENTRY_FIELDS) for item in rows)


def _module_entries(table: dict[Any, Any] | list[Any]) -> list[tuple[str, dict[str, Any]]]:
    """模块表里的每一项都进图鉴。少一条就失败，不在这里筛掉。"""
    if isinstance(table, list):
        pairs: list[tuple[Any, Any]] = [(str(index), value) for index, value in enumerate(table, start=1)]
        named = False
    else:
        pairs = list(table.items())
        named = True
    rows: list[tuple[str, dict[str, Any]]] = []
    for key, value in pairs:
        if not isinstance(value, dict) or (named and (not isinstance(key, str) or not key)):
            raise Ror2WikiError(f"模块条目无法对应到图鉴：{key!r}")
        name = (_text(value.get("Name")) or str(key)) if named else _text(value.get("Name"))
        if not name:
            raise Ror2WikiError(f"模块条目没有名字：{key}")
        rows.append((name, value))
    if len(rows) != len(table):
        raise Ror2WikiError("图鉴条数和模块条目不一致")
    return rows


def _item_from_entry(name: str, entry: dict[str, Any], *, default_rarity: str) -> Ror2ItemOut:
    image = None if entry.get("NoIcon") is True else wiki_file_url(f"{name}.png")
    return Ror2ItemOut(
        name=name,
        rarity=_text(entry.get("Rarity")) or default_rarity,
        quote=_text(entry.get("Quote")),
        description=_text(entry.get("Desc") or entry.get("Description")),
        categories=_strings(entry.get("Category")),
        unlock=_text(entry.get("Unlock")),
        expansion=_text(entry.get("Expansion")),
        internal_name=_text(entry.get("LocalizationInternalName")),
        code=_text(entry.get("ID")),
        corrupt=_text(entry.get("Corrupt")),
        uncorrupt=_text(entry.get("Uncorrupt")),
        boss=_text(entry.get("Boss")),
        cooldown=_text(entry.get("Cooldown")),
        wiki_url=wiki_page_url(name),
        image_url=image,
        stats=_stats(entry.get("Stats")),
    )


def _survivor_from_entry(name: str, entry: dict[str, Any]) -> Ror2SurvivorOut:
    image_name = _text(entry.get("Image")) or f"{name}.png"
    return Ror2SurvivorOut(
        name=name,
        umbra=_text(entry.get("Umbra")),
        description=_text(entry.get("Description")),
        unlock=_text(entry.get("Unlock")),
        expansion=_text(entry.get("Expansion")),
        phrase_escape=_text(entry.get("PhraseEscape")),
        phrase_vanish=_text(entry.get("PhraseVanish")),
        health=_num(entry.get("BaseHealth")),
        health_per_level=_num(entry.get("ScalingHealth")),
        damage=_num(entry.get("BaseDamage")),
        damage_per_level=_num(entry.get("ScalingDamage")),
        regen=_num(entry.get("BaseHealthRegen")),
        regen_per_level=_num(entry.get("ScalingHealthRegen")),
        speed=_num(entry.get("BaseSpeed")),
        armor=_num(entry.get("BaseArmor")),
        wiki_url=wiki_page_url(name),
        image_url=None if entry.get("NoIcon") is True else wiki_file_url(image_name),
    )


def _monster_from_entry(name: str, entry: dict[str, Any]) -> Ror2MonsterOut:
    return Ror2MonsterOut(
        name=name,
        kind=_text(entry.get("Type")),
        role=_text(entry.get("Class")),
        expansion=_text(entry.get("Expansion")),
        boss_name=_text(entry.get("BossName")),
        categories=_strings(entry.get("Category")),
        is_ally=entry.get("IsAlly") is True,
        do_not_count=entry.get("DoNotCount") is True,
        is_subtype=entry.get("SubType") is True,
        wiki_url=wiki_page_url(_wiki_title(entry, name)),
        image_url=_file_image(entry.get("Image")),
        **_combat(entry),
    )


def _drone_from_entry(name: str, entry: dict[str, Any]) -> Ror2DroneOut:
    return Ror2DroneOut(
        name=name,
        kind=_text(entry.get("Type")),
        quote=_text(entry.get("Quote")),
        description=_text(entry.get("Desc") or entry.get("Description")),
        rarity=_text(entry.get("Rarity")),
        type2=_text(entry.get("Type2")),
        cost=_price(entry.get("BaseCost"), entry.get("Currency")),
        wiki_url=wiki_page_url(_wiki_title(entry, name)),
        image_url=_file_image(entry.get("Image")),
        **_combat(entry),
    )


def _environment_from_entry(name: str, entry: dict[str, Any]) -> Ror2EnvironmentOut:
    return Ror2EnvironmentOut(
        name=name,
        stage=_text(entry.get("Stage")),
        subtitle=_text(entry.get("SubName")),
        description=_text(entry.get("Description")),
        soundtrack=_text(entry.get("Soundtrack")),
        lunar_seer=_text(entry.get("LunarSeer")),
        expansion=_text(entry.get("Expansion")),
        wiki_url=wiki_page_url(_wiki_title(entry, name)),
        image_url=_file_image(entry.get("Image")),
    )


def _challenge_from_entry(name: str, entry: dict[str, Any]) -> Ror2ChallengeOut:
    return Ror2ChallengeOut(
        name=name,
        kind=_text(entry.get("Type")),
        description=_text(entry.get("Desc") or entry.get("Description")),
        unlock=_strings(entry.get("Unlock")),
        coins=_text(entry.get("Coins")),
        expansion=_text(entry.get("Expansion")),
        wiki_url=wiki_page_url(name),
    )


def _interactable_from_entry(name: str, entry: dict[str, Any]) -> Ror2InteractableOut:
    purchase = entry.get("Purchase")
    cost = ""
    if isinstance(purchase, dict):
        cost = _price(purchase.get("Cost"), purchase.get("Type"))
    return Ror2InteractableOut(
        name=name,
        category=_text(entry.get("Category")),
        effect=_text(entry.get("Effect")),
        expansion=_text(entry.get("Expansion")),
        cost=cost,
        link=_text(entry.get("NameLink")) or name,
        location=_strings(entry.get("Location")),
        wiki_url=wiki_page_url(_wiki_title(entry, name)),
        image_url=_file_image(entry.get("ImageLink") or entry.get("Image")),
    )


def _artifact_from_entry(name: str, entry: dict[str, Any]) -> Ror2ArtifactOut:
    return Ror2ArtifactOut(
        name=name,
        description=_text(entry.get("Desc") or entry.get("Description")),
        code=_strings(entry.get("Code")),
        expansion=_text(entry.get("Expansion")),
        unlock=_text(entry.get("Unlock")),
        wiki_url=wiki_page_url(name),
        image_url=wiki_file_url(f"Artifact_of_{name}.png"),
    )


def _combat(entry: dict[str, Any]) -> dict[str, float | None]:
    return {
        "health": _num(entry.get("BaseHealth")),
        "health_per_level": _num(entry.get("ScalingHealth")),
        "damage": _num(entry.get("BaseDamage")),
        "damage_per_level": _num(entry.get("ScalingDamage")),
        "regen": _num(entry.get("BaseHealthRegen")),
        "regen_per_level": _num(entry.get("ScalingHealthRegen")),
        "speed": _num(entry.get("BaseSpeed")),
        "armor": _num(entry.get("BaseArmor")),
    }


_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _file_image(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name.lower().endswith(_IMAGE_EXT):
        return None
    return wiki_file_url(name)


def _wiki_title(entry: dict[str, Any], name: str) -> str:
    for key in ("Link", "NameLink"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return name


def _price(cost: Any, kind: Any) -> str:
    cost_text = _text(cost)
    kind_text = _text(kind)
    if cost_text and kind_text:
        return f"{cost_text} {kind_text}"
    return cost_text or kind_text


def _stats(value: Any) -> list[Ror2StatOut]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = list(value.values())
    else:
        return []
    out: list[Ror2StatOut] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = _text(row.get("Stat") or row.get("Name"))
        if not label:
            continue
        out.append(
            Ror2StatOut(
                label=label,
                value=_text(row.get("Value")),
                stack=_text(row.get("Stack")),
                add=_text(row.get("Add")),
            )
        )
    return out


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, dict):
        raw = list(value.values())
    else:
        raw = [value]
    return [text for item in raw if (text := _text(item))]


def _text(value: Any) -> str:
    if isinstance(value, str):
        return plain_wikitext(value)
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return ""


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _item_sort(item: Ror2ItemOut) -> tuple[int, str]:
    try:
        rank = _RARITY_ORDER.index(item.rarity)
    except ValueError:
        rank = len(_RARITY_ORDER)
    return rank, item.name.casefold()


def _dict_keys(value: dict[Any, Any]) -> list[str]:
    return sorted(str(key) for key in value)


def fetched_at_text(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")
