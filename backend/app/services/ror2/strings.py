"""Wiki 展示字符串的稳定编号，以及原文指纹。

有 ``LocalizationInternalName`` 的物品、装备、怪物、无人机用这个令牌。
其余条目用 Wiki 英文名编号，例如 ``survivor.Commando.name``。
编号进 Weblate，不在页面上另做一层覆盖。

指纹把原文规范成 NFC、换行收成 ``\\n``、去掉每行行尾空白和首尾空行，再取 SHA-256。
已审译文只有在这份指纹和当前 Wiki 原文一致时才展示。
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.services.ror2.schemas import (
    Ror2CatalogOut,
    Ror2ItemOut,
    Ror2SurvivorDetailOut,
    Ror2SurvivorOut,
    Ror2WikiBlockOut,
    Ror2WikiItemOut,
)


class Ror2StringError(Exception):
    pass


@dataclass(frozen=True)
class StringSlot:
    id: str
    source: str
    write: Callable[[str], None]


def normalize_source(text: str) -> str:
    """指纹用的原文。空字符串表示这段不入册。"""
    normalized = unicodedata.normalize("NFC", text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_source(text).encode("utf-8")).hexdigest()


def translation_for(units: dict[str, dict[str, str]], string_id: str, source: str) -> str:
    """已审、且原文指纹和当前 Wiki 一致，才返回译文。"""
    row = units.get(string_id)
    if not isinstance(row, dict) or row.get("state") != "approved":
        return ""
    target = row.get("target")
    stored = row.get("source")
    if not isinstance(target, str) or not target.strip() or not isinstance(stored, str):
        return ""
    if fingerprint(stored) != fingerprint(source):
        return ""
    return target


def catalog_sources(catalog: Ror2CatalogOut) -> dict[str, str]:
    return _sources(catalog_slots(catalog))


def detail_sources(detail: Ror2SurvivorDetailOut) -> dict[str, str]:
    return _sources(detail_slots(detail))


def merge_sources(*groups: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for group in groups:
        for key, source in group.items():
            previous = merged.get(key)
            if previous is not None and previous != source:
                raise Ror2StringError(f"编号冲突：{key}")
            merged[key] = source
    return merged


def apply_catalog(catalog: Ror2CatalogOut, units: dict[str, dict[str, str]]) -> None:
    _apply(catalog_slots(catalog), units)


def apply_detail(detail: Ror2SurvivorDetailOut, units: dict[str, dict[str, str]]) -> None:
    _apply(detail_slots(detail), units)


def prefill_catalog(catalog: Ror2CatalogOut, strings: dict[str, str]) -> dict[str, str]:
    """用已经落库的游戏中文给 Weblate 提建议。建议不是页面译文。"""
    from app.services.ror2.lang import apply_item_language, apply_survivor_language

    suggestions: dict[str, str] = {}
    if not strings:
        return suggestions
    items = [row.model_copy() for row in catalog.items]
    equipment = [row.model_copy() for row in catalog.equipment]
    survivors = [row.model_copy() for row in catalog.survivors]
    apply_item_language(items, strings)
    apply_item_language(equipment, strings)
    apply_survivor_language(survivors, strings)
    _prefill_named(suggestions, "item", catalog.items, items)
    _prefill_named(suggestions, "equipment", catalog.equipment, equipment)
    for row, filled in zip(catalog.survivors, survivors, strict=True):
        if filled.name_zh:
            suggestions[f"survivor.{row.name}.name"] = filled.name_zh
    return suggestions


def prefill_detail(detail: Ror2SurvivorDetailOut, strings: dict[str, str]) -> dict[str, str]:
    from app.services.ror2.lang import apply_survivor_detail_language

    if not strings:
        return {}
    shadow = detail.model_copy(deep=True)
    apply_survivor_detail_language(shadow, strings)
    suggestions: dict[str, str] = {}
    if shadow.lore_zh:
        suggestions[f"survivor.{detail.name}.lore"] = shadow.lore_zh
    stems = _Stems()
    skills = [skill for group in detail.skills for skill in group.skills]
    filled = [skill for group in shadow.skills for skill in group.skills]
    for skill, translated in zip(skills, filled, strict=True):
        stem = stems.take(detail.name, skill.name)
        if translated.name_zh:
            suggestions[f"{stem}.name"] = translated.name_zh
        if translated.description_zh:
            suggestions[f"{stem}.desc"] = translated.description_zh
    return suggestions


def catalog_slots(catalog: Ror2CatalogOut) -> list[StringSlot]:
    slots: list[StringSlot] = []
    _named_rows(slots, "item", catalog.items)
    _named_rows(slots, "equipment", catalog.equipment)
    for row in catalog.survivors:
        _survivor_fields(slots, row)
    for row in catalog.monsters:
        base = _record_id("monster", row.name, row.internal_name)
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.boss", row.boss_name, _set(row, "boss_name_zh"))
    for row in catalog.drones:
        base = _record_id("drone", row.name, row.internal_name)
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
        _add(slots, f"{base}.quote", row.quote, _set(row, "quote_zh"))
    for row in catalog.environments:
        base = f"environment.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
        _add(slots, f"{base}.subtitle", row.subtitle, _set(row, "subtitle_zh"))
    for row in catalog.challenges:
        base = f"challenge.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
    for row in catalog.interactables:
        base = f"interactable.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.effect", row.effect, _set(row, "effect_zh"))
    for row in catalog.artifacts:
        base = f"artifact.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
        _add(slots, f"{base}.unlock", row.unlock, _set(row, "unlock_zh"))
    return slots


def detail_slots(detail: Ror2SurvivorDetailOut) -> list[StringSlot]:
    slots: list[StringSlot] = []
    base = f"survivor.{detail.name}"
    _add(slots, f"{base}.name", detail.name, _set(detail, "name_zh"))
    _add(slots, f"{base}.summary", detail.summary, _set(detail, "summary_zh"))
    _add(slots, f"{base}.umbra", detail.umbra, _set(detail, "umbra_zh"))
    _add(slots, f"{base}.phrase_escape", detail.phrase_escape, _set(detail, "phrase_escape_zh"))
    _add(slots, f"{base}.phrase_vanish", detail.phrase_vanish, _set(detail, "phrase_vanish_zh"))
    _add(slots, f"{base}.lore", detail.lore, _set(detail, "lore_zh"))
    stems = _Stems()
    for group in detail.skills:
        for skill in group.skills:
            stem = stems.take(detail.name, skill.name)
            _add(slots, f"{stem}.name", skill.name, _set(skill, "name_zh"))
            _add(slots, f"{stem}.desc", skill.description, _set(skill, "description_zh"))
            _add(slots, f"{stem}.unlock", skill.unlock, _set(skill, "unlock_zh"))
            _add_items(slots, f"{stem}.note", skill.notes)
    _add_blocks(slots, f"{base}.behavior", detail.behaviors)
    _add_blocks(slots, f"{base}.tip", detail.tips)
    _add_blocks(slots, f"{base}.trivia", detail.trivia)
    seen_versions: dict[str, int] = {}
    for index, group in enumerate(detail.history, start=1):
        label = group.version or str(index)
        count = seen_versions.get(label, 0) + 1
        seen_versions[label] = count
        stem = f"{base}.history.{label}" if count == 1 else f"{base}.history.{label}#{count}"
        _add_items(slots, stem, group.items)
    for index, image in enumerate(detail.gallery, start=1):
        _add(slots, f"{base}.gallery.{index}.caption", image.caption, _set(image, "caption_zh"))
    return slots


class _Stems:
    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def take(self, survivor: str, skill: str) -> str:
        base = f"skill.{survivor}.{skill}"
        count = self._seen.get(base, 0) + 1
        self._seen[base] = count
        if count == 1:
            return base
        return f"{base}#{count}"


def _survivor_fields(slots: list[StringSlot], row: Ror2SurvivorOut) -> None:
    base = f"survivor.{row.name}"
    _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
    _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
    _add(slots, f"{base}.umbra", row.umbra, _set(row, "umbra_zh"))
    _add(slots, f"{base}.unlock", row.unlock, _set(row, "unlock_zh"))
    _add(slots, f"{base}.phrase_escape", row.phrase_escape, _set(row, "phrase_escape_zh"))
    _add(slots, f"{base}.phrase_vanish", row.phrase_vanish, _set(row, "phrase_vanish_zh"))


def _named_rows(slots: list[StringSlot], kind: str, rows: list[Ror2ItemOut]) -> None:
    for row in rows:
        base = _record_id(kind, row.name, row.internal_name)
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))


def _prefill_named(
    suggestions: dict[str, str],
    kind: str,
    rows: list[Ror2ItemOut],
    filled: list[Ror2ItemOut],
) -> None:
    for row, translated in zip(rows, filled, strict=True):
        base = _record_id(kind, row.name, row.internal_name)
        if translated.name_zh:
            suggestions[f"{base}.name"] = translated.name_zh
        if translated.description_zh:
            suggestions[f"{base}.desc"] = translated.description_zh


def _record_id(kind: str, name: str, token: str) -> str:
    cleaned = token.strip()
    if cleaned:
        return f"{kind}.{cleaned}"
    return f"{kind}.wiki.{name}"


def _add(slots: list[StringSlot], string_id: str, source: str, write: Callable[[str], None]) -> None:
    if not normalize_source(source):
        return
    if any(ord(char) < 32 for char in string_id):
        raise Ror2StringError(f"编号里不能有控制字符：{string_id!r}")
    slots.append(StringSlot(string_id, source, write))


def _add_blocks(slots: list[StringSlot], prefix: str, blocks: list[Ror2WikiBlockOut]) -> None:
    for index, block in enumerate(blocks, start=1):
        stem = f"{prefix}.{index}"
        _add(slots, stem, block.text, _set(block, "text_zh"))
        _add_items(slots, stem, block.items)
        for image_index, image in enumerate(block.images, start=1):
            _add(
                slots,
                f"{stem}.image.{image_index}.caption",
                image.caption,
                _set(image, "caption_zh"),
            )


def _add_items(slots: list[StringSlot], prefix: str, items: list[Ror2WikiItemOut]) -> None:
    for index, item in enumerate(items, start=1):
        stem = f"{prefix}.{index}"
        _add(slots, stem, item.text, _set(item, "text_zh"))
        _add_items(slots, stem, item.children)


def _sources(slots: list[StringSlot]) -> dict[str, str]:
    found: dict[str, str] = {}
    for slot in slots:
        previous = found.get(slot.id)
        if previous is not None and previous != slot.source:
            raise Ror2StringError(f"编号冲突：{slot.id}")
        found[slot.id] = slot.source
    return found


def _apply(slots: list[StringSlot], units: dict[str, dict[str, str]]) -> None:
    if not units:
        return
    for slot in slots:
        text = translation_for(units, slot.id, slot.source)
        if text:
            slot.write(text)


def _set(obj: object, attr: str) -> Callable[[str], None]:
    def write(text: str, obj: object = obj, attr: str = attr) -> None:
        setattr(obj, attr, text)

    return write
