"""文章 HTML 入库消毒、封面 URL 校验。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import nh3

from app.services.articles.errors import ArticleError

_HTML_TAGS = {
    "p",
    "br",
    "hr",
    "span",
    "div",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "del",
    "mark",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "figure",
    "figcaption",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
_HTML_ATTRS = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "*": {"class"},
}
_HTML_URL_SCHEMES = {"http", "https", "mailto"}
_P_BLOCK = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_A_TAG = re.compile(r"<a\b[^>]*>.*?</a>", re.IGNORECASE | re.DOTALL)
_CLASS_ATTR = re.compile(r"\sclass=([\"'])([^\"']*)\1", re.IGNORECASE)
_ALLOWED_CLASS = re.compile(
    r"^(article-align-(?:left|center|right)|article-indent-[1-4]|"
    r"article-color-(?:red|orange|gold|green|blue|purple|gray)|"
    r"article-mark-(?:yellow|green|red|blue)|article-math(?:-block)?|"
    r"language-[\w-]+)$"
)
_COLOR_HEX = {
    "red": (207, 19, 34),
    "orange": (212, 107, 8),
    "gold": (212, 136, 6),
    "green": (56, 158, 13),
    "blue": (22, 119, 255),
    "purple": (83, 29, 171),
    "gray": (89, 89, 89),
}
_MARK_HEX = {
    "yellow": (255, 241, 184),
    "green": (217, 247, 190),
    "red": (255, 204, 199),
    "blue": (186, 224, 255),
}
_NAMED_COLORS = {
    "red": (255, 0, 0),
    "orange": (255, 165, 0),
    "gold": (255, 215, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "purple": (128, 0, 128),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "yellow": (255, 255, 0),
}
_OPEN_TAG = re.compile(
    r"<(span|mark|font|p|h[1-6]|blockquote|li|strong|b|em|i|u|s|del|td|th|div)(\s[^>]*)?>",
    re.IGNORECASE,
)
_FONT_CLOSE = re.compile(r"</font>", re.IGNORECASE)
_ATTR = re.compile(
    r"""(?:^|\s)([^\s=/>]+)\s*=\s*(?:(['"])(.*?)\2|([^\s>]+))""",
    re.IGNORECASE | re.DOTALL,
)
_RGB = re.compile(
    r"^rgba?\(\s*([0-9.]+)(%?)\s*[, ]\s*([0-9.]+)(%?)\s*[, ]\s*([0-9.]+)(%?)"
    r"(?:\s*[,/]\s*([0-9.]+))?\s*\)$"
)
_HEX = re.compile(r"^#([0-9a-f]{3}|[0-9a-f]{6})$")


def _channel(raw: str, percent: str) -> int:
    try:
        value = float(raw)
    except ValueError:
        return 0
    if percent:
        return max(0, min(255, round(value / 100 * 255)))
    return max(0, min(255, round(value)))


def parse_css_color(value: str | None) -> tuple[int, int, int] | None:
    text = (value or "").strip().lower()
    if not text or text in {"transparent", "inherit", "currentcolor"}:
        return None
    named = _NAMED_COLORS.get(text)
    if named:
        return named
    hex_match = _HEX.match(text)
    if hex_match:
        raw = hex_match.group(1)
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    rgb = _RGB.match(text)
    if rgb:
        alpha = 1.0 if rgb.group(7) is None else float(rgb.group(7))
        if alpha <= 0:
            return None
        return (
            _channel(rgb.group(1), rgb.group(2)),
            _channel(rgb.group(3), rgb.group(4)),
            _channel(rgb.group(5), rgb.group(6)),
        )
    return None


def _rgb_to_hsl(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in rgb)
    max_c, min_c = max(r, g, b), min(r, g, b)
    light = (max_c + min_c) / 2
    if max_c == min_c:
        return (0.0, 0.0, light)
    delta = max_c - min_c
    sat = delta / (2 - max_c - min_c) if light > 0.5 else delta / (max_c + min_c)
    if max_c == r:
        hue = (g - b) / delta + (6 if g < b else 0)
    elif max_c == g:
        hue = (b - r) / delta + 2
    else:
        hue = (r - g) / delta + 4
    return (hue * 60, sat, light)


def classify_article_color(rgb: tuple[int, int, int]) -> str | None:
    for key, value in _COLOR_HEX.items():
        if value == rgb:
            return key
    hue, sat, light = _rgb_to_hsl(rgb)
    if light < 0.12 or light > 0.88:
        return None
    if sat < 0.12:
        return "gray"
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 40:
        return "orange"
    if hue < 65:
        return "gold"
    if hue < 160:
        return "green"
    if hue < 260:
        return "blue"
    return "purple"


def classify_article_mark(rgb: tuple[int, int, int]) -> str | None:
    for key, value in _MARK_HEX.items():
        if value == rgb:
            return key
    hue, sat, light = _rgb_to_hsl(rgb)
    if sat < 0.12 or light > 0.97 or light < 0.35:
        return None
    if hue < 20 or hue >= 340:
        return "red"
    if hue < 80:
        return "yellow"
    if hue < 160:
        return "green"
    return "blue"


def _style_prop(style: str, name: str) -> str:
    match = re.search(rf"(?:^|;)\s*{re.escape(name)}\s*:\s*([^;]+)", style or "", re.I)
    return match.group(1).strip() if match else ""


def _parse_attrs(raw: str) -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = []
    pos = 0
    text = raw or ""
    for match in _ATTR.finditer(text):
        if match.start() > pos:
            leftover = text[pos : match.start()].strip()
            if leftover:
                for token in leftover.split():
                    out.append((token, None))
        name = match.group(1)
        value = match.group(3) if match.group(3) is not None else match.group(4) or ""
        out.append((name, value))
        pos = match.end()
    leftover = text[pos:].strip()
    if leftover:
        for token in leftover.split():
            out.append((token, None))
    return out


def _attr_value(attrs: list[tuple[str, str | None]], name: str) -> str:
    for key, value in reversed(attrs):
        if key.lower() == name.lower() and value is not None:
            return value
    return ""


def _rewrite_open_tag(match: re.Match[str]) -> str:
    tag = match.group(1)
    attrs = _parse_attrs(match.group(2) or "")
    style = _attr_value(attrs, "style")
    classes = [token for token in _attr_value(attrs, "class").split() if token]
    color_key = next((c[14:] for c in classes if c.startswith("article-color-")), "")
    mark_key = next((c[13:] for c in classes if c.startswith("article-mark-")), "")
    if not color_key:
        rgb = parse_css_color(_style_prop(style, "color") or _attr_value(attrs, "color"))
        color_key = classify_article_color(rgb) if rgb else ""
    if not mark_key:
        bg = parse_css_color(
            _style_prop(style, "background-color") or _style_prop(style, "background")
        )
        mark_key = classify_article_mark(bg) if bg else ""
    if tag.lower() == "mark" and not mark_key:
        mark_key = "yellow"
    if color_key and f"article-color-{color_key}" not in classes:
        classes.append(f"article-color-{color_key}")
    if mark_key and f"article-mark-{mark_key}" not in classes:
        classes.append(f"article-mark-{mark_key}")
    next_tag = "span" if tag.lower() == "font" else tag
    kept: list[str] = []
    for key, value in attrs:
        lower = key.lower()
        if lower in {"style", "color", "class"}:
            continue
        if value is None:
            kept.append(key)
        else:
            quote = "'" if '"' in value else '"'
            kept.append(f"{key}={quote}{value}{quote}")
    if classes:
        kept.insert(0, f'class="{" ".join(classes)}"')
    attr_text = f" {' '.join(kept)}" if kept else ""
    return f"<{next_tag}{attr_text}>"


def promote_palette_styles(html: str) -> str:
    """把 Halo/Word 的 style 颜色提升成白名单 class，再丢掉 style。"""
    promoted = _OPEN_TAG.sub(_rewrite_open_tag, html or "")
    return _FONT_CLOSE.sub("</span>", promoted)


def filter_article_classes(html: str) -> str:
    def repl(match: re.Match[str]) -> str:
        quote = match.group(1)
        kept = [token for token in match.group(2).split() if _ALLOWED_CLASS.match(token)]
        if not kept:
            return ""
        return f" class={quote}{' '.join(kept)}{quote}"

    return _CLASS_ATTR.sub(repl, html or "")


def sanitize_html(body: str) -> str:
    return filter_article_classes(
        nh3.clean(
            promote_palette_styles(body or ""),
            tags=_HTML_TAGS,
            attributes=_HTML_ATTRS,
            url_schemes=_HTML_URL_SCHEMES,
            link_rel="noopener noreferrer",
            clean_content_tags={"script", "style"},
        )
    )


def split_adjacent_file_links(html: str) -> str:
    """Halo 附件常挤在同一个 p、中间没空白，拆成列表以免文件名连成一串。"""

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        links = _A_TAG.findall(inner)
        if len(links) < 2:
            return match.group(0)
        leftover = _A_TAG.sub("", inner)
        if leftover.strip():
            return match.group(0)
        items = "".join(f"<li>{link}</li>" for link in links)
        return f"<ul>{items}</ul>"

    return _P_BLOCK.sub(repl, html or "")


def prepare_article_body(body: str, body_format: str) -> str:
    text = body or ""
    if body_format == "html":
        return split_adjacent_file_links(sanitize_html(text))
    return text


def normalize_cover_url(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.startswith("/") and not text.startswith("//"):
        if "\\" in text or ".." in text or ":" in text.split("?", 1)[0]:
            raise ArticleError(400, "封面链接无效")
        return text
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return text
    raise ArticleError(400, "封面链接无效")
