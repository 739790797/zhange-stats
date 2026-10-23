"""把每份 Wiki 原文拆成可增量翻译的字符串。

Lua 数据表按路径走。条目若有 LocalizationInternalName，字段挂在这个令牌下，显示名单独一条。
普通文章页的章节和表头走语义上下文，不依赖空行段落序号。
"""

from __future__ import annotations

import hashlib
import re

from app.services.ror2.lua_data import LuaModuleError, parse_lua_module
from app.services.ror2.strings import Ror2StringError, normalize_source
from app.services.ror2.wiki_structure import (
    WIKI_ARTICLE_PREFIX,
    WIKI_EXPANSION_PREFIX,
    article_title_from_resource,
    parse_article,
    parse_expansion_article,
    WikiStructureError,
)

_SKIP_KEYS = frozenset(
    {
        "LocalizationInternalName",
        "InternalName",
        "Internal",
        "ID",
        "Image",
        "NoIcon",
    }
)
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
_NUMBER = re.compile(r"^[+-]?\d+(?:\.\d+)?%?$")
_IMAGE = re.compile(r"\.(?:png|gif|jpe?g|webp)$", re.IGNORECASE)


def extract_units(resource: str, body: str) -> dict[str, str]:
    """resource 是 guide_raws 的资源名。返回 Weblate context -> 原文。"""
    if resource.startswith(WIKI_ARTICLE_PREFIX):
        return article_units(resource, body, article_title_from_resource(resource))
    if resource.startswith(WIKI_EXPANSION_PREFIX):
        try:
            article = parse_expansion_article(resource, body)
        except WikiStructureError as exc:
            raise Ror2StringError(str(exc)) from exc
        return {article.title.context: article.title.text}
    try:
        data = parse_lua_module(body)
    except LuaModuleError:
        if resource.startswith("survivor/"):
            return article_units(resource, body, resource.partition("/")[2], include_title=False) | _paragraphs(
                resource, body, stable=True
            )
        return _paragraphs(resource, body)
    root = data.get("return")
    if not isinstance(root, dict):
        root = {key: value for key, value in data.items() if key != "return"}
    units: dict[str, str] = {}
    _walk(root, resource, units)
    return units


def article_units(resource: str, body: str, title: str, *, include_title: bool = True) -> dict[str, str]:
    try:
        parsed = parse_article(resource, title, body)
    except WikiStructureError as exc:
        raise Ror2StringError(str(exc)) from exc
    units: dict[str, str] = {}
    if include_title and parsed.title.text:
        units[parsed.title.context] = parsed.title.text
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


def _walk(value: object, path: str, units: dict[str, str], *, token_shared: bool = False) -> None:
    if isinstance(value, str):
        _put(units, path, value)
        return
    if isinstance(value, dict):
        base, renamed = _rebase(value, path, shared=token_shared)
        if renamed:
            _put(units, f"{base}.name", renamed)
        counts = _token_counts(value)
        for key, child in value.items():
            if isinstance(key, str) and key in _SKIP_KEYS:
                continue
            segment = _segment(key)
            if not segment:
                continue
            shared = False
            if isinstance(child, dict):
                token = child.get("LocalizationInternalName")
                if isinstance(token, str) and counts.get(token, 0) > 1:
                    shared = True
            child_path = f"{base}.{segment}" if base else segment
            _walk(child, child_path, units, token_shared=shared)
        return
    if isinstance(value, list):
        for index, child in enumerate(value, start=1):
            _walk(child, f"{path}.{index}", units)


def _rebase(value: dict, path: str, *, shared: bool) -> tuple[str, str]:
    token = value.get("LocalizationInternalName")
    if not isinstance(token, str) or not _TOKEN.match(token) or not path:
        return path, ""
    parent, sep, leaf = path.rpartition(".")
    if not sep or not leaf or leaf == token:
        return path, ""
    if shared:
        base = f"{parent}.{token}.{leaf}" if parent else f"{token}.{leaf}"
    else:
        base = f"{parent}.{token}" if parent else token
    return base, leaf


def _token_counts(value: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for child in value.values():
        if not isinstance(child, dict):
            continue
        token = child.get("LocalizationInternalName")
        if isinstance(token, str) and _TOKEN.match(token):
            counts[token] = counts.get(token, 0) + 1
    return counts


def _put(units: dict[str, str], key: str, text: str) -> None:
    if _skip_text(text) or _skip_key(key):
        return
    previous = units.get(key)
    if previous is not None and previous != text:
        raise Ror2StringError(f"编号冲突：{key}")
    units[key] = text


def _skip_text(text: str) -> bool:
    if not normalize_source(text):
        return True
    stripped = text.strip()
    if _TOKEN.match(stripped) or _NUMBER.match(stripped):
        return True
    if stripped.startswith(("http://", "https://")):
        return True
    return bool(_IMAGE.search(stripped))


def _skip_key(key: str) -> bool:
    return any(ord(char) < 32 for char in key)


def _segment(key: object) -> str:
    if isinstance(key, str):
        text = key.strip()
        return "" if not text or _skip_key(text) else text
    if isinstance(key, int) and not isinstance(key, bool):
        return str(key)
    return ""


def _paragraphs(resource: str, body: str, *, stable: bool = False) -> dict[str, str]:
    units: dict[str, str] = {}
    blocks: list[str] = []
    buf: list[str] = []
    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.strip():
            if buf:
                blocks.append("\n".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        blocks.append("\n".join(buf))
    occurrences: dict[str, int] = {}
    for index, block in enumerate(blocks, start=1):
        if stable:
            normalized = normalize_source(block)
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
            count = occurrences.get(digest, 0) + 1
            occurrences[digest] = count
            suffix = digest if count == 1 else f"{digest}~{count}"
            key = f"{resource}.paragraph.{suffix}"
        else:
            key = f"{resource}.{index}"
        _put(units, key, block)
    return units