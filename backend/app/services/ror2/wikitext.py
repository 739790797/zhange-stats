"""把 Wiki 描述收成可展示的文本。颜色和层数保留成游戏样式标签。"""

from __future__ import annotations

import html
import re

_LINK = re.compile(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]")
_MARKUP = re.compile(r"'''?|</?[^>]+>")
_SPACE = re.compile(r"[ \t]*\n[ \t]*|[ \t]{2,}")
_HEX = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3}){0,2}")
_ALLOWED_TAG = re.compile(
    r"^</?(?:style(?:=[A-Za-z0-9_]+)?|color(?:=#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3}){0,2})?|u)>$",
    re.IGNORECASE,
)
# Wiki Color 快捷名里，和游戏 TMP 样式表色值一致的，换成对应样式名。
_COLOR_STYLE = {
    "d": "cIsDamage",
    "damage": "cIsDamage",
    "h": "cIsHealing",
    "heal": "cIsHealing",
    "healing": "cIsHealing",
    "u": "cIsUtility",
    "utility": "cIsUtility",
    "hp": "cIsHealth",
    "health": "cIsHealth",
    "death": "cDeath",
    "v": "cIsVoid",
    "void": "cIsVoid",
    "artifact": "cArtifact",
    "boss": "cIsTierBoss",
    "yellow": "cIsTierBoss",
    "temporary": "cIsTemporary",
    "temp": "cIsTemporary",
}
# 游戏样式表里没有同名样式、但 Wiki Color 模板写了色值的快捷名。
_WIKI_COLOR_HEX = {
    "hallowed": "#9368F9",
    "lunar": "#307FFF",
}


def plain_wikitext(text: str) -> str:
    """``{{Color|d|15%}}`` 保留为 ``<style=cIsDamage>15%</style>``。单参数模板去掉。"""
    raw = html.unescape(text or "")
    flattened = _templates(raw)
    flattened = _LINK.sub(r"\1", flattened)
    flattened = _strip_markup(flattened)
    flattened = _SPACE.sub(" ", flattened)
    return flattened.strip()


def _strip_markup(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("<") and _ALLOWED_TAG.match(token):
            return token
        return ""

    return _MARKUP.sub(repl, text)


def _templates(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("{{", i):
            end = _template_end(text, i)
            inner = text[i + 2 : end - 2]
            out.append(_template_visible(inner))
            i = end
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _template_end(text: str, start: int) -> int:
    depth = 0
    j = start
    n = len(text)
    while j < n - 1:
        if text.startswith("{{", j):
            depth += 1
            j += 2
            continue
        if text.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                return j
            continue
        j += 1
    return n


def _template_visible(inner: str) -> str:
    parts = _split_pipes(_templates(inner))
    name = parts[0].strip().lower() if parts else ""
    if name == "color":
        return _color_template(parts)
    if name == "stack":
        body = parts[1].strip() if len(parts) > 1 else ""
        return f"<style=cStack>{body}</style>" if body else ""
    visible = [part.strip() for part in parts if part.strip()]
    if len(visible) <= 1:
        return ""
    return visible[-1]


def _color_template(parts: list[str]) -> str:
    if len(parts) < 3:
        return ""
    key = parts[1].strip()
    body = parts[2].strip()
    style = _COLOR_STYLE.get(key.lower())
    wiki_hex = _WIKI_COLOR_HEX.get(key.lower())
    if style:
        wrapped = f"<style={style}>{body}</style>"
    elif wiki_hex:
        wrapped = f"<color={wiki_hex}>{body}</color>"
    elif _HEX.fullmatch(key):
        wrapped = f"<color={key}>{body}</color>"
    else:
        wrapped = body
    if len(parts) > 3 and parts[3].strip():
        return f"<u>{wrapped}</u>"
    return wrapped


def _split_pipes(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("{{", i):
            depth += 1
            buf.append("{{")
            i += 2
            continue
        if text.startswith("}}", i) and depth:
            depth -= 1
            buf.append("}}")
            i += 2
            continue
        if text[i] == "|" and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(text[i])
        i += 1
    parts.append("".join(buf))
    return parts
