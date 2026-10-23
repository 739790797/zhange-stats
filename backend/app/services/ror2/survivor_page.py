"""幸存者词条：属性来自幸存者模块，技能和日志来自各自的数据模块，其余段落来自词条原文。"""

from __future__ import annotations

import re
from typing import Any

from app.services.ror2.catalog import Ror2WikiError, wiki_file_url
from app.services.ror2.lua_data import parse_lua_module
from app.services.ror2.schemas import (
    Ror2GalleryImageOut,
    Ror2HistoryOut,
    Ror2SkillGroupOut,
    Ror2SkillOut,
    Ror2SurvivorDetailOut,
    Ror2SurvivorOut,
    Ror2WikiBlockOut,
    Ror2WikiItemOut,
)
from app.services.ror2.wikitext import inline_wikitext

_HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$")
_LIST = re.compile(r"^([#*]+)\s*(.*)$")
_FILE = re.compile(r"\[\[File:([^|\]]+?)(?:\|[^\]]*)?\]\]", re.IGNORECASE)
_GALLERY = re.compile(r"<gallery\b[^>]*>(.*?)</gallery>", re.IGNORECASE | re.DOTALL)
_HR = re.compile(r"<hr\s*/?>", re.IGNORECASE)
_DIV = re.compile(r"</?div\b[^>]*>", re.IGNORECASE)
_EXPANSIONS = {
    "sotv": "SotV",
    "sots": "SotS",
    "ac": "AC",
    "hc": "HC",
}
_SECTION_KEYS = {
    "skills": "skills",
    "behaviors": "behaviors",
    "tips": "tips",
    "lore": "lore",
    "version history": "history",
    "gallery": "gallery",
    "trivia": "trivia",
}


class Ror2MissingSurvivor(Exception):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


def survivor_page_resource(name: str) -> str:
    return f"survivor/{name}"


def skills_table(src: str) -> dict[str, Any]:
    return _named_table(src, "skills", "没有技能表")


def lore_table(src: str) -> dict[str, Any]:
    return _named_table(src, "lore", "没有日志表")


def accept_survivor_page(body: str) -> None:
    if "{{SurvivorPage" not in body:
        raise Ror2WikiError("不是幸存者词条")


def build_survivor_detail(
    survivor: Ror2SurvivorOut,
    page: str,
    skills: dict[str, Any],
    lore: dict[str, Any],
) -> Ror2SurvivorDetailOut:
    lead, sections = _sections(page.replace("{{PAGENAME}}", survivor.name))
    return Ror2SurvivorDetailOut(
        name=survivor.name,
        name_zh=survivor.name_zh,
        summary=lead or inline_wikitext(survivor.description),
        umbra=survivor.umbra,
        phrase_escape=survivor.phrase_escape,
        phrase_vanish=survivor.phrase_vanish,
        expansion=survivor.expansion,
        health=survivor.health,
        health_per_level=survivor.health_per_level,
        regen=survivor.regen,
        regen_per_level=survivor.regen_per_level,
        damage=survivor.damage,
        damage_per_level=survivor.damage_per_level,
        speed=survivor.speed,
        acceleration=survivor.acceleration,
        mass=survivor.mass,
        armor=survivor.armor,
        image_url=survivor.image_url,
        wiki_url=survivor.wiki_url,
        lore=lore_text(lore, survivor.name),
        skills=_skill_groups(sections.get("skills", ""), skills),
        behaviors=_prose(sections.get("behaviors", "")),
        tips=_prose(sections.get("tips", "")),
        trivia=_prose(sections.get("trivia", "")),
        gallery=_gallery(sections.get("gallery", "")),
        history=_history(sections.get("history", "")),
    )


def _named_table(src: str, key: str, error: str) -> dict[str, Any]:
    try:
        module = parse_lua_module(src)
    except Exception as exc:
        raise Ror2WikiError(f"模块解析失败：{exc}") from exc
    found = module.get(key)
    if not isinstance(found, dict) or not found:
        container = module.get("p")
        nested = container.get(key) if isinstance(container, dict) else None
        found = nested if isinstance(nested, dict) else None
    if not isinstance(found, dict) or not found:
        raise Ror2WikiError(error)
    return found


def _sections(page: str) -> tuple[str, dict[str, str]]:
    lead: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in page.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        heading = _HEADING.match(line.strip())
        if heading and len(heading.group(1)) == 2:
            title = heading.group(2).strip().casefold()
            current = _SECTION_KEYS.get(title, "")
            if current:
                sections.setdefault(current, [])
            continue
        if current is None:
            lead.append(line)
        elif current:
            sections[current].append(line)
    summary = inline_wikitext("\n".join(lead).replace("__TOC__", ""))
    return summary, {key: "\n".join(lines) for key, lines in sections.items()}


def lore_text(lore: dict[str, Any], name: str) -> str:
    entry = lore.get(name)
    if not isinstance(entry, dict):
        return ""
    desc = entry.get("Desc")
    if not isinstance(desc, str):
        return ""
    return inline_wikitext(desc)


def _skill_groups(text: str, skills: dict[str, Any]) -> list[Ror2SkillGroupOut]:
    groups: list[Ror2SkillGroupOut] = []
    for name, inner in _top_templates(text):
        if name.casefold() != "skilltype":
            continue
        parts = _split_args(inner)
        skill_type = parts[1].strip() if len(parts) > 1 else ""
        body = "|".join(parts[2:]) if len(parts) > 2 else ""
        rows: list[Ror2SkillOut] = []
        for skill_name, skill_inner in _top_templates(body):
            if skill_name.casefold() != "skill":
                continue
            skill = _skill(skill_type, skill_inner, skills)
            if skill.name:
                rows.append(skill)
        if skill_type and rows:
            groups.append(Ror2SkillGroupOut(skill_type=skill_type, skills=rows))
    return groups


def _skill(skill_type: str, inner: str, skills: dict[str, Any]) -> Ror2SkillOut:
    params = _named(inner)
    name = params.get("name", "").strip()
    entry = skills.get(name) if isinstance(skills.get(name), dict) else {}
    description = entry.get("Desc") if isinstance(entry, dict) else ""
    unlock = entry.get("Unlock") if isinstance(entry, dict) else ""
    icon = name.replace(":", "").strip()
    return Ror2SkillOut(
        name=name,
        skill_type=params.get("type", "").strip() or skill_type,
        cooldown=params.get("cooldown", "").strip(),
        proc=params.get("proc", "").strip(),
        description=inline_wikitext(description) if isinstance(description, str) else "",
        notes=_list_items(params.get("notes", ""), "*"),
        unlock=inline_wikitext(unlock) if isinstance(unlock, str) else "",
        image_url=wiki_file_url(f"{icon}.png") if icon else None,
    )


def _named(inner: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in _split_args(inner)[1:]:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        found[key.strip().casefold()] = value.strip()
    return found


def _prose(text: str) -> list[Ror2WikiBlockOut]:
    text, galleries = _take_galleries(text)
    blocks = _blocks(text)
    if galleries:
        blocks.append(Ror2WikiBlockOut(kind="images", images=galleries))
    return blocks


def _blocks(text: str) -> list[Ror2WikiBlockOut]:
    blocks: list[Ror2WikiBlockOut] = []
    paragraph: list[str] = []
    lines = _clean_lines(text)

    def flush() -> None:
        if not paragraph:
            return
        body = inline_wikitext(" ".join(paragraph))
        paragraph.clear()
        if body:
            blocks.append(Ror2WikiBlockOut(kind="p", text=body))

    index = 0
    while index < len(lines):
        line = lines[index]
        matched = _LIST.match(line)
        if matched:
            flush()
            marker = matched.group(1)[0]
            gathered: list[tuple[int, str]] = []
            while index < len(lines):
                item = _LIST.match(lines[index])
                if not item or item.group(1)[0] != marker:
                    break
                gathered.append((len(item.group(1)), item.group(2)))
                index += 1
            blocks.append(
                Ror2WikiBlockOut(
                    kind="ol" if marker == "#" else "ul",
                    items=_list_tree(gathered),
                )
            )
            continue
        if line.startswith(";"):
            flush()
            body = inline_wikitext(line.lstrip(";").strip())
            if body:
                blocks.append(Ror2WikiBlockOut(kind="p", text=body))
            index += 1
            continue
        paragraph.append(line)
        index += 1
    flush()
    return blocks


def _list_items(text: str, marker: str) -> list[Ror2WikiItemOut]:
    gathered: list[tuple[int, str]] = []
    for line in _clean_lines(text):
        matched = _LIST.match(line)
        if matched and matched.group(1)[0] == marker:
            gathered.append((len(matched.group(1)), matched.group(2)))
        elif line and not gathered:
            gathered.append((1, line))
        elif line:
            gathered.append((2, line))
    return _list_tree(gathered)


def _list_tree(rows: list[tuple[int, str]]) -> list[Ror2WikiItemOut]:
    root: list[Ror2WikiItemOut] = []
    stack: list[tuple[int, list[Ror2WikiItemOut]]] = [(0, root)]
    for depth, text in rows:
        node = Ror2WikiItemOut(text=inline_wikitext(text))
        while len(stack) > 1 and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1].append(node)
        stack.append((depth, node.children))
    return root


def _history(text: str) -> list[Ror2HistoryOut]:
    groups: list[Ror2HistoryOut] = []
    for chunk in _HR.split(_DIV.sub("", text)):
        version = ""
        body: list[str] = []
        for line in _clean_lines(chunk):
            if line.startswith(";") and not version:
                version = inline_wikitext(line.lstrip(";").strip())
                continue
            body.append(line)
        items = _list_items("\n".join(body), "*")
        if version or items:
            groups.append(Ror2HistoryOut(version=version, items=items))
    return groups


def _gallery(text: str) -> list[Ror2GalleryImageOut]:
    text, loose = _take_galleries(text)
    rows = _table_rows(text)
    images = _zip_gallery(rows)
    return images or loose


def _zip_gallery(rows: list[list[str]]) -> list[Ror2GalleryImageOut]:
    parsed = [[_cell_image(cell) for cell in row] for row in rows]
    parsed = [row for row in parsed if any(cell and cell[0] for cell in row)]
    if not parsed:
        return []
    if len(parsed) >= 3:
        stills, spins, captions = parsed[0], parsed[1], parsed[2]
        images: list[Ror2GalleryImageOut] = []
        for index, still in enumerate(stills):
            if not still or not still[0]:
                continue
            spin = spins[index][0] if index < len(spins) and spins[index] else None
            caption = captions[index] if index < len(captions) and captions[index] else None
            images.append(
                Ror2GalleryImageOut(
                    image_url=still[0],
                    spin_url=spin,
                    caption=caption[1] if caption else "",
                    expansion=caption[2] if caption else "",
                )
            )
        return images
    images = []
    for row in parsed:
        for cell in row:
            if cell and cell[0]:
                images.append(Ror2GalleryImageOut(image_url=cell[0], caption=cell[1], expansion=cell[2]))
    return images


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    current: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if line.startswith("{|") or line.startswith("|}"):
            continue
        if line.startswith("|-"):
            if current:
                rows.append(current)
                current = []
            continue
        if not line.startswith("|"):
            continue
        for cell in line.split("||"):
            cell = cell.strip()
            if cell.startswith("|"):
                cell = cell[1:].strip()
            if cell:
                current.append(cell)
    if current:
        rows.append(current)
    return rows


def _cell_image(cell: str) -> tuple[str, str, str] | None:
    matched = _FILE.search(cell)
    if not matched:
        return None
    expansion = ""
    for name, code in _EXPANSIONS.items():
        if re.search(rf"\{{\{{\s*{name}\b", cell, re.IGNORECASE):
            expansion = code
            break
    caption = inline_wikitext(_FILE.sub("", cell))
    return wiki_file_url(matched.group(1).strip()), caption, expansion


def _take_galleries(text: str) -> tuple[str, list[Ror2GalleryImageOut]]:
    images: list[Ror2GalleryImageOut] = []

    def repl(match: re.Match[str]) -> str:
        for line in match.group(1).splitlines():
            line = line.strip()
            if not line.lower().startswith("file:"):
                continue
            name, _, caption = line[5:].partition("|")
            cleaned = name.strip()
            if cleaned:
                images.append(
                    Ror2GalleryImageOut(image_url=wiki_file_url(cleaned), caption=inline_wikitext(caption))
                )
        return ""

    return _GALLERY.sub(repl, text), images


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line or line == "__TOC__" or line.startswith("<div") or line.startswith("</div"):
            continue
        if line.startswith("{|") or line.startswith("|}") or line.startswith("|-") or line.startswith("|"):
            continue
        lines.append(line)
    return lines


def _top_templates(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        start = text.find("{{", index)
        if start < 0:
            break
        end = _template_end(text, start)
        inner = text[start + 2 : end - 2]
        name = _split_args(inner)[0].strip()
        if name:
            found.append((name, inner))
        index = end
    return found


def _template_end(text: str, start: int) -> int:
    depth = 0
    index = start
    while index < len(text) - 1:
        if text.startswith("{{", index):
            depth += 1
            index += 2
            continue
        if text.startswith("}}", index):
            depth -= 1
            index += 2
            if depth == 0:
                return index
            continue
        index += 1
    return len(text)


def _split_args(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    curly = 0
    square = 0
    index = 0
    while index < len(inner):
        if inner.startswith("{{", index):
            curly += 1
            buf.append("{{")
            index += 2
            continue
        if inner.startswith("}}", index) and curly:
            curly -= 1
            buf.append("}}")
            index += 2
            continue
        if inner.startswith("[[", index):
            square += 1
            buf.append("[[")
            index += 2
            continue
        if inner.startswith("]]", index) and square:
            square -= 1
            buf.append("]]")
            index += 2
            continue
        if inner[index] == "|" and curly == 0 and square == 0:
            parts.append("".join(buf))
            buf = []
            index += 1
            continue
        buf.append(inner[index])
        index += 1
    parts.append("".join(buf))
    return parts
