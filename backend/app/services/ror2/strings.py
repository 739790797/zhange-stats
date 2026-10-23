"""Wiki 页面字符串的稳定逻辑编号，以及原文指纹。

有 ``LocalizationInternalName`` 的物品、装备、怪物、无人机优先用这个令牌。
Weblate 快照保留源语言文件的上下文键；展示时按显式资源、记录身份和字段映射到页面槽。

指纹把原文规范成 NFC、换行收成 ``\n``、去掉每行行尾空白和首尾空行，再取 SHA-256。
已审译文只有在原文指纹与当前 Wiki 内容一致时才展示；上下文映射还会按页面使用的 Wiki 文本格式归一标签。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.services.ror2.schemas import (
    Ror2CatalogOut,
    Ror2ItemOut,
    Ror2SurvivorDetailOut,
    Ror2SurvivorOut,
    Ror2TextOut,
    Ror2WikiBlockOut,
    Ror2WikiItemOut,
)
from app.services.ror2.wikitext import inline_wikitext, plain_wikitext

_TAG_TOKEN = re.compile(
    r"</?(?P<name>style|color|u|b|i)"
    r"(?:=(?P<value>#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3}){0,2}|[A-Za-z0-9_]+))?>",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(
    r"(?<![A-Za-z0-9_%])%(?:%|(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|L|z|j|t)?[diouxXfFeEgGaAcspn])"
    r"|(?<!\{)\{(?:\d+|[A-Za-z_][A-Za-z0-9_.-]*)(?::[^{}]+)?\}(?!\})"
)


class Ror2StringError(Exception):
    pass


@dataclass(frozen=True)
class StringSlot:
    id: str
    source: str
    write: Callable[[str], None]
    context_resource: str = ""
    context_name: str = ""
    context_token: str = ""
    context_field: str = ""
    source_format: Literal["inline", "plain"] = "inline"
    context_id: str = ""
    context_suffix: str = ""
    require_context: bool = False


_CONTEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "name": ("name", "Name"),
    "desc": ("Desc", "Description"),
    # The official game language uses _PICKUP for the Wiki item quote field.
    "quote": ("Quote", "_PICKUP", "Pickup"),
    "boss": ("BossName",),
    "umbra": ("Umbra",),
    "unlock": ("Unlock",),
    "phrase_escape": ("PhraseEscape",),
    "phrase_vanish": ("PhraseVanish",),
    "subtitle": ("SubName",),
    "effect": ("Effect",),
    "rarity": ("Rarity",),
    "stack": ("Stack",),
}


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


def resolve_catalog_texts(
    catalog: Ror2CatalogOut,
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
) -> dict[str, Ror2TextOut]:
    return _resolve_slots(catalog_slots(catalog), sources, units)


def resolve_detail_texts(
    detail: Ror2SurvivorDetailOut,
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
) -> dict[str, Ror2TextOut]:
    return _resolve_slots(detail_slots(detail), sources, units)


def slot_result_key(string_id: str, context_name: str = "", context_token: str = "") -> str:
    """同一个 LocalizationInternalName 对应多个 Wiki 名称时保持槽位互不覆盖。"""
    return f"{string_id}::record:{context_name}" if context_token else string_id


def resolve_context_text(
    original: str,
    context: str,
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
    *,
    source_format: Literal["inline", "plain"] = "plain",
) -> Ror2TextOut:
    """语义文章单元使用解析器给出的真实 Weblate context，不造逻辑 ID。"""
    return _resolve_exact_context(original, context, sources, units, source_format=source_format)


def apply_catalog(
    catalog: Ror2CatalogOut,
    units: dict[str, dict[str, str]],
    sources: dict[str, str] | None = None,
) -> None:
    _apply(catalog_slots(catalog), units, sources or {})


def apply_detail(
    detail: Ror2SurvivorDetailOut,
    units: dict[str, dict[str, str]],
    sources: dict[str, str] | None = None,
) -> None:
    _apply(detail_slots(detail), units, sources or {})


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
        context = {
            "context_resource": "enemies",
            "context_name": row.name,
            "context_token": row.internal_name,
            "source_format": "plain",
        }
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"), context_field="name", **context)
        _add(slots, f"{base}.boss", row.boss_name, _set(row, "boss_name_zh"), context_field="boss", **context)
    for row in catalog.drones:
        base = _record_id("drone", row.name, row.internal_name)
        context = {
            "context_resource": "enemies",
            "context_name": row.name,
            "context_token": row.internal_name,
            "source_format": "plain",
        }
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"), context_field="name", **context)
        _add(
            slots,
            f"{base}.desc",
            row.description,
            _set(row, "description_zh"),
            context_field="desc",
            **context,
        )
        _add(slots, f"{base}.quote", row.quote, _set(row, "quote_zh"), context_field="quote", **context)
    for row in catalog.environments:
        base = f"environment.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
        _add(slots, f"{base}.subtitle", row.subtitle, _set(row, "subtitle_zh"))
    for row in catalog.challenges:
        base = f"challenge.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"))
        context = {
            "context_resource": "challenges",
            "context_name": row.name,
            "source_format": "plain",
            "context_field": "unlock",
        }
        for index, name in enumerate(row.unlock, start=1):
            _add(slots, f"{base}.unlock.{index}", name, lambda _text: None, **context)
    for row in catalog.interactables:
        base = f"interactable.wiki.{row.name}"
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"))
        _add(slots, f"{base}.effect", row.effect, _set(row, "effect_zh"))
    for row in catalog.artifacts:
        base = f"artifact.wiki.{row.name}"
        context = {"context_resource": "artifacts", "context_name": row.name, "source_format": "plain"}
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"), context_field="name", **context)
        _add(
            slots,
            f"{base}.desc",
            row.description,
            _set(row, "description_zh"),
            context_field="desc",
            **context,
        )
        _add(slots, f"{base}.unlock", row.unlock, _set(row, "unlock_zh"), context_field="unlock", **context)
    return slots


def detail_slots(detail: Ror2SurvivorDetailOut) -> list[StringSlot]:
    slots: list[StringSlot] = []
    base = f"survivor.{detail.name}"
    survivor_context = {"context_resource": "survivors", "context_name": detail.name, "source_format": "plain"}
    _add(slots, f"{base}.name", detail.name, _set(detail, "name_zh"), context_field="name", **survivor_context)
    _add(
        slots,
        f"{base}.summary",
        detail.summary,
        _set(detail, "summary_zh"),
        context_field="desc",
        **survivor_context,
    )
    _add(slots, f"{base}.umbra", detail.umbra, _set(detail, "umbra_zh"), context_field="umbra", **survivor_context)
    _add(
        slots,
        f"{base}.phrase_escape",
        detail.phrase_escape,
        _set(detail, "phrase_escape_zh"),
        context_field="phrase_escape",
        **survivor_context,
    )
    _add(
        slots,
        f"{base}.phrase_vanish",
        detail.phrase_vanish,
        _set(detail, "phrase_vanish_zh"),
        context_field="phrase_vanish",
        **survivor_context,
    )
    _add(
        slots,
        f"{base}.lore",
        detail.lore,
        _set(detail, "lore_zh"),
        context_resource="lore",
        context_name=detail.name,
        context_field="desc",
        source_format="inline",
    )
    stems = _Stems()
    for group_index, group in enumerate(detail.skills, start=1):
        _add(slots, f"{base}.skill_group.{group_index}.title", group.skill_type, lambda _text: None)
        for skill in group.skills:
            _add(slots, f"{base}.skill_group.{group_index}.skill_type.{skill.name}", skill.skill_type, lambda _text: None)
            stem = stems.take(detail.name, skill.name)
            skill_context = {
                "context_resource": "skills",
                "context_name": skill.name,
                "source_format": "inline",
            }
            _add(slots, f"{stem}.name", skill.name, _set(skill, "name_zh"), context_field="name", **skill_context)
            _add(
                slots,
                f"{stem}.desc",
                skill.description,
                _set(skill, "description_zh"),
                context_field="desc",
                **skill_context,
            )
            _add(
                slots,
                f"{stem}.unlock",
                skill.unlock,
                _set(skill, "unlock_zh"),
                context_field="unlock",
                **skill_context,
            )
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
        _add(slots, f"{stem}.version", group.version, lambda _text: None)
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
    context = {"context_resource": "survivors", "context_name": row.name, "source_format": "plain"}
    _add(slots, f"{base}.name", row.name, _set(row, "name_zh"), context_field="name", **context)
    _add(slots, f"{base}.desc", row.description, _set(row, "description_zh"), context_field="desc", **context)
    _add(slots, f"{base}.umbra", row.umbra, _set(row, "umbra_zh"), context_field="umbra", **context)
    _add(slots, f"{base}.unlock", row.unlock, _set(row, "unlock_zh"), context_field="unlock", **context)
    _add(
        slots,
        f"{base}.phrase_escape",
        row.phrase_escape,
        _set(row, "phrase_escape_zh"),
        context_field="phrase_escape",
        **context,
    )
    _add(
        slots,
        f"{base}.phrase_vanish",
        row.phrase_vanish,
        _set(row, "phrase_vanish_zh"),
        context_field="phrase_vanish",
        **context,
    )


def _named_rows(slots: list[StringSlot], kind: str, rows: list[Ror2ItemOut]) -> None:
    resource = {"item": "items", "equipment": "equipment"}.get(kind, "")
    for row in rows:
        base = _record_id(kind, row.name, row.internal_name)
        context = {
            "context_resource": resource,
            "context_name": row.name,
            "context_token": row.internal_name,
            "source_format": "plain",
        }
        _add(
            slots,
            f"{base}.rarity",
            row.rarity,
            _set(row, "rarity_zh"),
            context_field="rarity",
            require_context=True,
            **context,
        )
        for index, stat in enumerate(row.stats, start=1):
            source_key = stat.source_key if stat.source_key is not None else f"unmapped-{index}"
            _add(
                slots,
                f"{base}.stats.{source_key}.stack",
                stat.stack,
                _set(stat, "stack_zh"),
                context_field="stack" if stat.source_key is not None else "",
                context_suffix=f"Stats.{source_key}.Stack" if stat.source_key is not None else "",
                require_context=True,
                **context,
            )
        _add(slots, f"{base}.name", row.name, _set(row, "name_zh"), context_field="name", **context)
        _add(
            slots,
            f"{base}.desc",
            row.description,
            _set(row, "description_zh"),
            context_field="desc",
            **context,
        )
        _add(
            slots,
            f"{base}.lore",
            row.lore,
            _set(row, "lore_zh"),
            context_resource="lore",
            context_name=row.name,
            context_field="desc",
            source_format="inline",
        )
        _add(slots, f"{base}.quote", row.quote, _set(row, "quote_zh"), context_field="quote", **context)
        _add(slots, f"{base}.unlock", row.unlock, _set(row, "unlock_zh"), context_field="unlock", **context)


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


def _add(
    slots: list[StringSlot],
    string_id: str,
    source: str,
    write: Callable[[str], None],
    *,
    context_resource: str = "",
    context_name: str = "",
    context_token: str = "",
    context_field: str = "",
    source_format: Literal["inline", "plain"] = "inline",
    context_id: str = "",
    context_suffix: str = "",
    require_context: bool = False,
) -> None:
    if not normalize_source(source):
        return
    if any(ord(char) < 32 for char in string_id):
        raise Ror2StringError(f"编号里不能有控制字符：{string_id!r}")
    slots.append(
        StringSlot(
            id=string_id,
            source=source,
            write=write,
            context_resource=context_resource,
            context_name=context_name,
            context_token=context_token,
            context_field=context_field,
            source_format=source_format,
            context_id=context_id,
            context_suffix=context_suffix,
            require_context=require_context,
        )
    )


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


def _apply(
    slots: list[StringSlot],
    units: dict[str, dict[str, str]],
    sources: dict[str, str],
) -> None:
    resolved = _resolve_slots(slots, sources, units)
    for slot in slots:
        value = resolved[slot_result_key(slot.id, slot.context_name, slot.context_token)]
        if value.text != value.original:
            slot.write(value.text)


def _resolve_slots(
    slots: list[StringSlot],
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
) -> dict[str, Ror2TextOut]:
    context_index = _context_index(sources)
    source_value_index = _source_value_index(sources, {slot.source_format for slot in slots})
    token_names: dict[tuple[str, str], set[str]] = {}
    for slot in slots:
        if slot.context_resource and slot.context_token and slot.context_name:
            token_names.setdefault((slot.context_resource, slot.context_token), set()).add(slot.context_name)
    resolved: dict[str, Ror2TextOut] = {}
    for slot in slots:
        context = _slot_context(slot, sources, context_index, source_value_index, token_names)
        value = _resolve_exact_context(
            slot.source,
            context,
            sources,
            units,
            source_format=slot.source_format,
        )
        result_key = slot_result_key(slot.id, slot.context_name, slot.context_token)
        resolved[result_key] = value
        # Retain a legacy lookup for unambiguous IDs; token-bearing duplicates
        # are projected through their name-qualified result key above.
        resolved.setdefault(slot.id, value)
    return resolved


def _context_index(sources: dict[str, str]) -> dict[tuple[str, str], list[tuple[str, str]]]:
    found: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for context, source in sources.items():
        if not isinstance(context, str) or not isinstance(source, str):
            continue
        resource, separator, remainder = context.partition(".")
        if not separator:
            continue
        _, separator, field = remainder.rpartition(".")
        if not separator or not field:
            continue
        found.setdefault((resource, field), []).append((context, source))
    return found


def _source_value_index(
    sources: dict[str, str],
    formats: set[Literal["inline", "plain"]],
) -> dict[tuple[Literal["inline", "plain"], str], list[str]]:
    found: dict[tuple[Literal["inline", "plain"], str], list[str]] = {}
    for source_format in formats:
        for context, source in sources.items():
            if not isinstance(context, str) or not isinstance(source, str):
                continue
            key = (source_format, fingerprint(_render_source(source, source_format)))
            found.setdefault(key, []).append(context)
    return found


def _slot_context(
    slot: StringSlot,
    sources: dict[str, str],
    context_index: dict[tuple[str, str], list[tuple[str, str]]],
    source_value_index: dict[tuple[Literal["inline", "plain"], str], list[str]],
    token_names: dict[tuple[str, str], set[str]],
) -> str:
    if slot.context_id:
        return slot.context_id
    fields = _CONTEXT_FIELDS.get(slot.context_field, ())
    if slot.context_resource and slot.context_name and fields:
        candidates = [
            (context, source)
            for field in fields
            for context, source in context_index.get((slot.context_resource, field), [])
            if _context_identity_matches(context, slot, token_names)
        ]
        if slot.context_suffix:
            candidates = [
                (context, source)
                for context, source in candidates
                if context.endswith(f".{slot.context_suffix}")
            ]
        if candidates:
            matches = [
                context
                for context, source in candidates
                if _source_matches(source, slot.source, slot.source_format)
            ]
            return matches[0] if len(matches) == 1 else ""
    if slot.require_context:
        return ""
    # For semantic text without a known Lua field mapping, only a globally
    # unique source fingerprint may attach a context; never use StringSlot.id.
    identity = fingerprint(_render_source(slot.source, slot.source_format))
    matches = source_value_index.get((slot.source_format, identity), [])
    return matches[0] if len(matches) == 1 else ""


def _context_identity_matches(
    context: str,
    slot: StringSlot,
    token_names: dict[tuple[str, str], set[str]],
) -> bool:
    if not context.startswith(f"{slot.context_resource}."):
        return False
    if slot.context_token:
        if not _has_context_segment(context, slot.context_token):
            return False
        names = token_names.get((slot.context_resource, slot.context_token), set())
        return len(names) <= 1 or _has_context_segment(context, slot.context_name)
    return _has_context_segment(context, slot.context_name)


def _has_context_segment(context: str, value: str) -> bool:
    return bool(value) and f".{value}." in f".{context}."


def _render_source(text: str, source_format: Literal["inline", "plain"]) -> str:
    return plain_wikitext(text) if source_format == "plain" else inline_wikitext(text)


def _source_matches(source: str, current: str, source_format: Literal["inline", "plain"]) -> bool:
    return fingerprint(_render_source(source, source_format)) == fingerprint(_render_source(current, source_format))


def _resolve_exact_context(
    original: str,
    context: str,
    sources: dict[str, str],
    units: dict[str, dict[str, str]],
    *,
    source_format: Literal["inline", "plain"],
) -> Ror2TextOut:
    source = sources.get(context) if context else None
    if not isinstance(source, str) or not _source_matches(source, original, source_format):
        return Ror2TextOut(text=original, original=original, token=None)
    token = context
    row = units.get(context)
    translation = ""
    if isinstance(row, dict) and row.get("state") == "approved":
        stored_source = row.get("source")
        target = row.get("target")
        if (
            isinstance(stored_source, str)
            and isinstance(target, str)
            and target.strip()
            and _source_matches(stored_source, original, source_format)
            and fingerprint(stored_source) == fingerprint(source)
            and _translation_structure_matches(source, target, source_format)
        ):
            translation = _render_source(target, source_format)
    if not translation.strip():
        translation = original
    return Ror2TextOut(text=translation, original=original, token=token)

def _translation_structure_matches(
    source: str,
    target: str,
    source_format: Literal["inline", "plain"],
) -> bool:
    source_text = _render_source(source, source_format)
    target_text = _render_source(target, source_format)
    source_tags = _rich_tag_signature(source_text)
    target_tags = _rich_tag_signature(target_text)
    return (
        source_tags is not None
        and target_tags is not None
        # Chinese word order may reorder or split equivalent styling spans.
        and set(source_tags) == set(target_tags)
        and sorted(_PLACEHOLDER.findall(source_text)) == sorted(_PLACEHOLDER.findall(target_text))
        and source_text.count("\n") == target_text.count("\n")
        and source_text.count(r"\n") == target_text.count(r"\n")
    )


def _rich_tag_signature(text: str) -> tuple[str, ...] | None:
    tags: list[str] = []
    stack: list[str] = []
    for match in _TAG_TOKEN.finditer(text):
        token = match.group(0)
        name = match.group("name").casefold()
        value = match.group("value")
        closing = token.startswith("</")
        if closing:
            if value is not None or not stack or stack.pop() != name:
                return None
        else:
            stack.append(name)
        tags.append(f"{'/' if closing else ''}{name}={value or ''}")
    if stack:
        return None
    return tuple(tags)


def _set(obj: object, attr: str) -> Callable[[str], None]:
    def write(text: str, obj: object = obj, attr: str = attr) -> None:
        setattr(obj, attr, text)

    return write
