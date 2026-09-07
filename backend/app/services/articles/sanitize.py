"""文章 HTML 入库消毒、封面 URL 校验。"""

from __future__ import annotations

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
    "img": {"src", "alt", "title"},
    "*": {"class"},
}
_HTML_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_html(body: str) -> str:
    return nh3.clean(
        body or "",
        tags=_HTML_TAGS,
        attributes=_HTML_ATTRS,
        url_schemes=_HTML_URL_SCHEMES,
        link_rel="noopener noreferrer",
        clean_content_tags={"script", "style"},
    )


def prepare_article_body(body: str, body_format: str) -> str:
    text = body or ""
    if body_format == "html":
        return sanitize_html(text)
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
