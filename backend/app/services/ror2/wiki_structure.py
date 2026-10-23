"""普通 Wiki 文章中的标题与表头：用语义路径生成稳定字符串上下文。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.ror2.wikitext import inline_wikitext

WIKI_ARTICLE_TITLES = (
    "Items",
    "Equipment",
    "Survivors",
    "Monsters",
    "Drones",
    "Environments",
    "Challenges",
    "Interactables",
    "Artifacts",
)
WIKI_ARTICLE_PREFIX = "wiki-page/"
WIKI_EXPANSION_PREFIX = "wiki-expansion/"
WIKI_EXPANSION_TITLES = {
    "SotV": "Survivors of the Void",
    "SotS": "Seekers of the Storm",
    "AC": "Alloyed Collective",
    "HC": "Hallowed Concepts",
}
WIKI_EXPANSION_ARTICLE_ID_PREFIX = "expansion:"
_HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$")


class WikiStructureError(ValueError):
    """普通 Wiki 文章的表格标记不完整或无法安全解析。"""


@dataclass(frozen=True)
class SourceText:
    context: str
    text: str


@dataclass(frozen=True)
class ArticleColumn:
    id: str
    label: SourceText


@dataclass(frozen=True)
class ArticleTable:
    id: str
    caption: SourceText | None = None
    columns: tuple[ArticleColumn, ...] = ()


@dataclass(frozen=True)
class ArticleSection:
    id: str
    level: int
    title: SourceText
    tables: tuple[ArticleTable, ...] = ()


@dataclass(frozen=True)
class ArticleSource:
    id: str
    title: SourceText
    sections: tuple[ArticleSection, ...] = ()


@dataclass
class _SectionBuilder:
    id: str
    level: int
    title: SourceText
    tables: list[ArticleTable] = field(default_factory=list)


def article_resource(title: str) -> str:
    """生成无空格、可放入 guide_raws resource 的普通文章标识。"""
    return f"{WIKI_ARTICLE_PREFIX}{title.strip().replace(' ', '_')}"


def expansion_resource(code: str) -> str:
    """资料片页只为页面标题建 raw 资源，避免把整篇文章全部送入 Weblate。"""
    if code not in WIKI_EXPANSION_TITLES:
        raise ValueError(f"未知的雨中冒险 2 资料片代号：{code}")
    return f"{WIKI_EXPANSION_PREFIX}{code}"


def parse_expansion_article(resource: str, body: str) -> ArticleSource:
    """将已同步的 DLC 页面 raw 投影为单一稳定标题单元，不解析章节/表格。"""
    if not resource.startswith(WIKI_EXPANSION_PREFIX):
        raise WikiStructureError("资料片 raw resource 前缀无效")
    code = resource.removeprefix(WIKI_EXPANSION_PREFIX)
    title = WIKI_EXPANSION_TITLES.get(code)
    if not title:
        raise WikiStructureError(f"无法识别的资料片 raw resource：{resource}")
    if not body.strip():
        raise WikiStructureError(f"资料片 Wiki 页面正文为空：{title}")
    return ArticleSource(
        id=f"{WIKI_EXPANSION_ARTICLE_ID_PREFIX}{code}",
        title=SourceText(f"{resource}.title", title),
        sections=(),
    )


def article_title_from_resource(resource: str) -> str:
    if not resource.startswith(WIKI_ARTICLE_PREFIX):
        return ""
    return resource.removeprefix(WIKI_ARTICLE_PREFIX).replace("_", " ")


def parse_article(resource: str, title: str, body: str) -> ArticleSource:
    """仅提取标题、章节和表格标签；段落正文仍由原页面解析器负责。"""
    root = f"{resource}.section"
    title_text = _visible(title)
    title_unit = SourceText(f"{resource}.title", title_text)
    sections: list[_SectionBuilder] = []
    heading_counts: dict[str, int] = {}
    current_id = "lead"
    current_level = 0
    current_title: SourceText | None = None
    tables_by_section: dict[str, list[ArticleTable]] = {}
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        heading = _HEADING.match(raw)
        if heading:
            visible = _visible(heading.group(2))
            if visible:
                base = _slug(visible)
                count = heading_counts.get(base, 0) + 1
                heading_counts[base] = count
                section_id = base if count == 1 else f"{base}~{count}"
                current_id = section_id
                current_level = len(heading.group(1))
                current_title = SourceText(f"{root}.{section_id}.title", visible)
                sections.append(_SectionBuilder(section_id, current_level, current_title))
            index += 1
            continue
        if raw.startswith("|}"):
            raise WikiStructureError(f"第 {index + 1} 行有未配对的表格结束标记")
        if raw.startswith("{|"):
            table_lines: list[str] = []
            depth = 1
            index += 1
            while index < len(lines):
                table_line = lines[index].strip()
                if table_line.startswith("{|"):
                    depth += 1
                elif table_line.startswith("|}"):
                    depth -= 1
                    if depth == 0:
                        break
                elif depth == 1:
                    table_lines.append(table_line)
                index += 1
            if depth != 0:
                raise WikiStructureError(f"第 {index + 1} 行之前的表格没有结束标记")
            table = _parse_table(resource, current_id, table_lines, tables_by_section)
            if table is not None:
                if current_title is None:
                    current_title = SourceText(f"{root}.lead.title", title_text)
                    sections.insert(0, _SectionBuilder("lead", 0, current_title))
                builder = next((row for row in sections if row.id == current_id), None)
                if builder is None:
                    builder = _SectionBuilder("lead", 0, current_title)
                    sections.insert(0, builder)
                builder.tables.append(table)
            index += 1
            continue
        index += 1
    return ArticleSource(
        id=resource.removeprefix(WIKI_ARTICLE_PREFIX),
        title=title_unit,
        sections=tuple(ArticleSection(row.id, row.level, row.title, tuple(row.tables)) for row in sections),
    )


def article_units(resource: str, body: str) -> dict[str, str]:
    title = article_title_from_resource(resource)
    parsed = parse_article(resource, title, body)
    units = {parsed.title.context: parsed.title.text} if parsed.title.text else {}
    for section in parsed.sections:
        if section.title.text:
            units[section.title.context] = section.title.text
        for table in section.tables:
            if table.caption is not None and table.caption.text:
                units[table.caption.context] = table.caption.text
            for column in table.columns:
                if column.label.text:
                    units[column.label.context] = column.label.text
    return units


def _parse_table(
    resource: str,
    section_id: str,
    lines: list[str],
    tables_by_section: dict[str, list[ArticleTable]],
) -> ArticleTable | None:
    raw_caption = ""
    raw_headers: list[str] = []
    for line in lines:
        if line.startswith("|+"):
            raw_caption = line[2:].strip()
        elif line.startswith("!"):
            raw_headers.extend(_header_cells(line[1:].strip()))
    headers = [visible for raw in raw_headers if (visible := _visible(_strip_cell_attributes(raw)))]
    caption_text = _visible(raw_caption) if raw_caption else ""
    if not caption_text and not headers:
        return None
    anchor = caption_text or headers[0]
    base = _slug(anchor)
    rows = tables_by_section.setdefault(section_id, [])
    duplicate_count = sum(row.id == base or row.id.startswith(f"{base}~") for row in rows)
    table_id = base if duplicate_count == 0 else f"{base}~{duplicate_count + 1}"
    table_prefix = f"{resource}.section.{section_id}.table.{table_id}"
    caption = SourceText(f"{table_prefix}.caption", caption_text) if caption_text else None
    column_counts: dict[str, int] = {}
    columns: list[ArticleColumn] = []
    for header in headers:
        column_slug = _slug(header)
        count = column_counts.get(column_slug, 0) + 1
        column_counts[column_slug] = count
        column_id = column_slug if count == 1 else f"{column_slug}~{count}"
        columns.append(ArticleColumn(column_id, SourceText(f"{table_prefix}.column.{column_id}", header)))
    parsed = ArticleTable(table_id, caption, tuple(columns))
    rows.append(parsed)
    return parsed


def _header_cells(value: str) -> list[str]:
    return [part.strip() for part in _split_top_level(value, "!!") if part.strip()]


def _strip_cell_attributes(value: str) -> str:
    parts = _split_top_level(value, "|")
    if len(parts) > 1 and "=" in parts[0]:
        return "|".join(parts[1:]).strip()
    return value.strip()


def _split_top_level(value: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    curly = 0
    square = 0
    while index < len(value):
        if value.startswith("{{", index):
            curly += 1
            index += 2
            continue
        if value.startswith("}}", index) and curly:
            curly -= 1
            index += 2
            continue
        if value.startswith("[[", index):
            square += 1
            index += 2
            continue
        if value.startswith("]]", index) and square:
            square -= 1
            index += 2
            continue
        if not curly and not square and value.startswith(delimiter, index):
            parts.append(value[start:index])
            index += len(delimiter)
            start = index
            continue
        index += 1
    parts.append(value[start:])
    return parts


def _visible(text: str) -> str:
    return inline_wikitext(text.replace("'''", "").replace("''", "")).strip()


def _slug(text: str) -> str:
    normalized = re.sub(r"[^\w]+", "_", text.strip().casefold(), flags=re.UNICODE).strip("_")
    return normalized or "section"