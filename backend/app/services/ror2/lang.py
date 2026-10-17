"""已经落库的游戏中文，只用来给 Weblate 提建议，不直接写到页面上。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.biz_logging import log_until_change
from app.models.guide_raw import GuideRaw
from app.services.ror2.schemas import Ror2ItemOut, Ror2SurvivorOut

log = logging.getLogger("zhange.ror2")

_LOG_KEY = "ror2-lang"
_NAME = "_NAME"
_DESC = "_DESC"
_DESCRIPTION = "_DESCRIPTION"
_LORE = "_LORE"
# Wiki 的 LocalizationInternalName 和游戏令牌不一致。只收对过的四条，不把旧版本指到现物品。
_TOKEN_ALIASES = {
    "ITEM_EXPODEONDEATH": "ITEM_EXPLODEONDEATH",
    "ITEM_LOWERHEALTHHIGHERDAMAGE": "ITEM_ATTACKSPEEDPERNEARBYALLYORENEMY",
    "ITEM_RESETCHESTS": "ITEM_ITEMDROPCHANCEONKILL",
    "ITEM_NEGATEATTACK": "ITEM_SPEEDBOOSTPICKUP",
}
_DLC_RE = re.compile(r"^DLC(\d+)", re.IGNORECASE)


class Ror2LangError(Exception):
    pass


def lang_file_sort_key(name: str) -> tuple[int, int, str]:
    """底稿在前，DLC 按编号在后。DLC10 排在 DLC4 后面，后读的键覆盖先读的。"""
    stem = Path(name).stem
    match = _DLC_RE.match(stem)
    if match:
        return (1, int(match.group(1)), name.lower())
    base_rank = 0 if name.lower() == "output.json" else 1
    return (0, base_rank, name.lower())


def string_table(body: str, name: str) -> dict[str, str]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise Ror2LangError(f"{name} 不是 JSON") from exc
    if not isinstance(payload, dict):
        raise Ror2LangError(f"{name} 不是 JSON 对象")
    nested = payload.get("strings", payload.get("Strings"))
    source = nested if isinstance(nested, dict) else payload
    table = {
        key: value
        for key, value in source.items()
        if isinstance(key, str) and isinstance(value, str) and "_" in key and key.upper() == key
    }
    return table


def merge_string_tables(tables: list[dict[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for table in tables:
        merged.update(table)
    return merged


def load_lang_strings(db: Session) -> dict[str, str]:
    """读已落库的 zh-CN。底稿在前，后编号的 DLC 覆盖同名键。没有语言文件时是空表。"""
    from sqlalchemy.orm import undefer

    from app.services.guide_raw.codec import unpack_raw_text

    rows = (
        db.query(GuideRaw)
        .options(undefer(GuideRaw.raw_body))
        .filter(GuideRaw.game == "ror2", GuideRaw.resource.like("zh-CN/%"))
        .all()
    )
    rows.sort(key=lambda row: lang_file_sort_key(row.resource.split("/", 1)[-1]))
    tables: list[dict[str, str]] = []
    for row in rows:
        try:
            tables.append(string_table(unpack_raw_text(row.raw_body), row.resource))
        except Ror2LangError:
            log_until_change(log, _LOG_KEY, "雨中冒险2语言文件跳过：%s", row.resource)
    return merge_string_tables(tables)


# 幸存者模块没有 LocalizationInternalName。这些是游戏角色体令牌，中文取自对应 _NAME。
_SURVIVOR_BODY = {
    "Commando": "COMMANDO_BODY",
    "Huntress": "HUNTRESS_BODY",
    "Bandit": "BANDIT2_BODY",
    "MUL-T": "TOOLBOT_BODY",
    "Engineer": "ENGI_BODY",
    "Artificer": "MAGE_BODY",
    "Mercenary": "MERC_BODY",
    "REX": "TREEBOT_BODY",
    "Loader": "LOADER_BODY",
    "Acrid": "CROCO_BODY",
    "Captain": "CAPTAIN_BODY",
    "Heretic": "HERETIC_BODY",
    "Railgunner": "RAILGUNNER_BODY",
    "Void Fiend": "VOIDSURVIVOR_BODY",
    "Seeker": "SEEKER_BODY",
    "False Son": "FALSESON_BODY",
    "CHEF": "CHEF_BODY",
    "Drifter": "DRIFTER_BODY",
    "Enforcer": "ENFORCER2_BODY",
    "Acolyte": "ACOLYTE_BODY",
    "Operator": "DRONETECH_BODY",
}


# 侍僧这四招的文本在 LILREAPER_*，不在 ACOLYTE_*。
_SKILL_NAME_STEM = {
    "Torrential Slash": "LILREAPER_PRIMARY",
    "Harrowing Chains": "LILREAPER_SECONDARY",
    "Soul Storm": "LILREAPER_UTILITY",
    "Banish": "LILREAPER_SPECIAL",
}
# 腐化形态沿用基础技能名。效果在 *_UPRADE_TOOLTIP，游戏文件里的键就是这个拼写。
_CORRUPT_UPGRADE = {
    "Corrupted Drown": "VOIDSURVIVOR_PRIMARY",
    "Corrupted Flood": "VOIDSURVIVOR_SECONDARY",
    "Corrupted Trespass": "VOIDSURVIVOR_UTILITY",
    "Corrupted Suppress": "VOIDSURVIVOR_SPECIAL",
}
_SKILL_SLOTS = ("PASSIVE", "PRIMARY", "SECONDARY", "UTILITY", "SPECIAL")
_SKILL_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")
_SKILL_TAG = re.compile(r"<[^>]+>")


def apply_survivor_detail_language(detail, strings: dict[str, str]) -> None:
    """建议用：日志和技能中文写进副本。对不上的名字留空，页面不读这份结果。"""
    from app.services.ror2.schemas import Ror2SurvivorDetailOut

    if not strings or not isinstance(detail, Ror2SurvivorDetailOut):
        return
    token = _SURVIVOR_BODY.get(detail.name)
    if not token:
        return
    lore = _lang_plain(strings.get(f"{token}{_LORE}", ""))
    if lore:
        detail.lore_zh = lore
    prefix = token.removesuffix("_BODY")
    stems = _skill_stems(prefix, strings)
    signatures = {stem: _skill_numbers(strings.get(f"{stem}{_DESCRIPTION}", "")) for stem in stems}
    skills = [skill for group in detail.skills for skill in group.skills]
    chosen = _assign_skill_stems(skills, prefix, stems, signatures)
    for skill, stem in zip(skills, chosen, strict=True):
        if not stem:
            continue
        name = _lang_plain(strings.get(f"{stem}{_NAME}", ""))
        desc = _lang_plain(strings.get(f"{stem}{_DESCRIPTION}", ""))
        if name:
            skill.name_zh = name
        if desc:
            skill.description_zh = desc
    for skill in skills:
        stem = _SKILL_NAME_STEM.get(skill.name)
        if stem:
            _write_skill_text(skill, strings, stem, f"{stem}{_DESCRIPTION}")
            continue
        base = _CORRUPT_UPGRADE.get(skill.name)
        if base:
            _write_skill_text(skill, strings, base, f"{base}_UPRADE_TOOLTIP")


def _write_skill_text(skill, strings: dict[str, str], name_stem: str, description_key: str) -> None:
    name = _lang_plain(strings.get(f"{name_stem}{_NAME}", ""))
    desc = _lang_plain(strings.get(description_key, ""))
    if name:
        skill.name_zh = name
    if desc:
        skill.description_zh = desc


def _lang_plain(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _skill_numbers(text: str) -> frozenset[str]:
    return frozenset(_SKILL_NUMBER.findall(_SKILL_TAG.sub("", text or "")))


def _skill_score(want: frozenset[str], got: frozenset[str]) -> int:
    if not want or not got:
        return 0
    overlap = len(want & got)
    if not overlap:
        return 0
    return overlap * 10 - len(got - want) * 3 - len(want - got)


def _stem_rank(stem: str, prefix: str, slot: str) -> tuple[int, int, str]:
    rest = stem[len(prefix) + 1 + len(slot) :]
    body = rest[1:] if rest.startswith("_") else rest
    if body == "":
        return (0, 0, "")
    if body == "ALT":
        return (1, 0, "")
    numbered = re.fullmatch(r"ALT(\d+)", body)
    if numbered:
        return (1, int(numbered.group(1)), "")
    return (2, 0, body)


def _skill_slot(stem: str, prefix: str) -> str:
    if not stem.startswith(prefix + "_"):
        return ""
    rest = stem[len(prefix) + 1 :]
    for slot in _SKILL_SLOTS:
        if rest == slot or rest.startswith(slot + "_"):
            return slot
    return ""


def _skill_stems(prefix: str, strings: dict[str, str]) -> list[str]:
    stems: list[str] = []
    for key in strings:
        if not key.endswith(_DESCRIPTION) or not key.startswith(prefix + "_"):
            continue
        stem = key[: -len(_DESCRIPTION)]
        if _skill_slot(stem, prefix):
            stems.append(stem)
    return stems


def _assign_skill_stems(skills, prefix: str, stems: list[str], signatures: dict[str, frozenset[str]]) -> list[str]:
    from app.services.ror2.schemas import Ror2SkillOut

    chosen = [""] * len(skills)
    by_slot: dict[str, list[int]] = {}
    for index, skill in enumerate(skills):
        if not isinstance(skill, Ror2SkillOut):
            continue
        by_slot.setdefault(skill.skill_type.upper(), []).append(index)
    for slot, indexes in by_slot.items():
        pool = [stem for stem in stems if _skill_slot(stem, prefix) == slot]
        _fill_skill_slot(indexes, skills, pool, signatures, chosen, prefix, slot)
    return chosen


def _fill_skill_slot(
    indexes,
    skills,
    pool: list[str],
    signatures: dict[str, frozenset[str]],
    chosen: list[str],
    prefix: str,
    slot: str,
) -> None:
    remaining_skills = list(indexes)
    remaining_stems = list(pool)
    blocked: set[tuple[int, str]] = set()
    while True:
        picked: tuple[int, str] | None = None
        ranked: list[tuple[int, int, str]] = []
        for index in remaining_skills:
            want = _skill_numbers(skills[index].description)
            if not want:
                continue
            for stem in remaining_stems:
                score = _skill_score(want, signatures[stem])
                if score > 0:
                    ranked.append((score, index, stem))
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
        for score, index, stem in ranked:
            if (index, stem) in blocked:
                continue
            want = _skill_numbers(skills[index].description)
            skill_rivals = [item for item in remaining_stems if _skill_score(want, signatures[item]) == score]
            stem_rivals = [
                item
                for item in remaining_skills
                if _skill_score(_skill_numbers(skills[item].description), signatures[stem]) == score
            ]
            if len(skill_rivals) == 1 and len(stem_rivals) == 1:
                picked = (index, stem)
                break
            blocked.add((index, stem))
        if picked is None:
            break
        index, stem = picked
        chosen[index] = stem
        remaining_skills.remove(index)
        remaining_stems.remove(stem)
    if remaining_skills and len(remaining_skills) == len(remaining_stems):
        skill_sigs = [_skill_numbers(skills[index].description) for index in remaining_skills]
        stem_sigs = [signatures[stem] for stem in remaining_stems]
        if skill_sigs[0] and all(sig == skill_sigs[0] for sig in skill_sigs + stem_sigs):
            ordered = sorted(remaining_stems, key=lambda stem: _stem_rank(stem, prefix, slot))
            for index, stem in zip(list(remaining_skills), ordered, strict=True):
                chosen[index] = stem
                remaining_skills.remove(index)
                remaining_stems.remove(stem)
    empty_skills = [index for index in remaining_skills if not _skill_numbers(skills[index].description)]
    empty_stems = [stem for stem in remaining_stems if not signatures[stem]]
    if empty_skills and len(empty_skills) == len(empty_stems):
        ordered = sorted(empty_stems, key=lambda stem: _stem_rank(stem, prefix, slot))
        for index, stem in zip(empty_skills, ordered, strict=True):
            chosen[index] = stem
            remaining_skills.remove(index)
            remaining_stems.remove(stem)
    base = f"{prefix}_{slot}"
    if base in remaining_stems and remaining_skills:
        chosen[remaining_skills[0]] = base
        remaining_stems.remove(base)
        remaining_skills.pop(0)


def apply_survivor_language(survivors: list[Ror2SurvivorOut], strings: dict[str, str]) -> None:
    """建议用：把角色名写进副本的 name_zh。页面不读这份结果。"""
    if not strings:
        return
    for row in survivors:
        token = _SURVIVOR_BODY.get(row.name)
        if not token:
            continue
        name = strings.get(f"{token}{_NAME}", "").strip()
        if name:
            row.name_zh = name


def apply_item_language(items: list[Ror2ItemOut], strings: dict[str, str]) -> None:
    """建议用：把物品中文写进副本。页面不读这份结果。"""
    if not strings:
        return
    for row in items:
        token = row.internal_name.strip()
        if not token:
            continue
        name = _lang_text(strings, token, _NAME)
        desc = _lang_text(strings, token, _DESC)
        if name:
            row.name_zh = name
        if desc:
            row.description_zh = desc


def _lang_text(strings: dict[str, str], token: str, suffix: str) -> str:
    direct = strings.get(f"{token}{suffix}", "").strip()
    if direct:
        return direct
    alias = _TOKEN_ALIASES.get(token)
    if not alias:
        return ""
    return strings.get(f"{alias}{suffix}", "").strip()


