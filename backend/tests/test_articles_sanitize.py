"""HTML 入库消毒与封面 URL。"""

from __future__ import annotations

import pytest

from app.services.articles.errors import ArticleError
from app.services.articles.sanitize import (
    classify_article_color,
    classify_article_mark,
    normalize_cover_url,
    parse_css_color,
    prepare_article_body,
    promote_palette_styles,
    sanitize_html,
    split_adjacent_file_links,
)
from app.services.articles import service as articles_svc
from tests.test_articles_service import _session, _user


def test_sanitize_html_strips_script_and_handlers() -> None:
    cleaned = sanitize_html(
        '<p onclick="alert(1)">ok</p><script>alert(1)</script>'
        '<a href="javascript:alert(1)">x</a>'
        '<img src="https://cdn.example/a.png" onerror="alert(1)">'
    )
    assert "script" not in cleaned.lower()
    assert "onclick" not in cleaned.lower()
    assert "onerror" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()
    assert "ok" in cleaned
    assert "https://cdn.example/a.png" in cleaned


def test_sanitize_html_keeps_table_span_and_palette_classes() -> None:
    cleaned = sanitize_html(
        '<table><tr><th colspan="2" class="article-align-center">头</th></tr>'
        '<tr><td rowspan="1" class="evil article-color-red">A</td>'
        '<td><mark class="article-mark-yellow">亮</mark></td></tr></table>'
    )
    assert 'colspan="2"' in cleaned or "colspan='2'" in cleaned or "colspan=" in cleaned
    assert "rowspan" in cleaned
    assert "article-align-center" in cleaned
    assert "article-color-red" in cleaned
    assert "article-mark-yellow" in cleaned
    assert "evil" not in cleaned
    assert "<mark" in cleaned


def test_sanitize_html_keeps_math_source_classes() -> None:
    cleaned = sanitize_html(
        '<p><span class="article-math evil">E=mc^2</span></p>'
        '<div class="article-math-block">\\frac{1}{2}</div>'
    )
    assert "article-math" in cleaned
    assert "article-math-block" in cleaned
    assert "E=mc^2" in cleaned
    assert "evil" not in cleaned


def test_sanitize_html_promotes_style_colors_to_classes() -> None:
    cleaned = sanitize_html(
        '<p><span style="color: rgb(231, 76, 60)">红</span>'
        '<mark style="background-color: #ffff00">亮</mark>'
        '<font color="#1677ff">蓝</font></p>'
    )
    assert "article-color-red" in cleaned
    assert "article-mark-yellow" in cleaned
    assert "article-color-blue" in cleaned
    assert "style=" not in cleaned
    assert "<font" not in cleaned.lower()
    assert parse_css_color("#1677ff") == (22, 119, 255)
    assert classify_article_color((22, 119, 255)) == "blue"
    assert classify_article_mark((255, 255, 0)) == "yellow"
    promoted = promote_palette_styles('<mark>亮</mark>')
    assert "article-mark-yellow" in promoted


def test_sanitize_html_keeps_local_article_images() -> None:
    cleaned = sanitize_html(
        '<figure><img src="/uploads/articles/halo/a.png" alt="图" width="800"></figure>'
    )
    assert "/uploads/articles/halo/a.png" in cleaned
    assert "width" in cleaned
    assert "<figure>" in cleaned


def test_split_adjacent_file_links() -> None:
    jammed = (
        "<p>"
        '<a href="/uploads/articles/halo/a.lml">a.lml</a>'
        '<a href="/uploads/articles/halo/b.lml">b.lml</a>'
        "</p>"
    )
    out = split_adjacent_file_links(jammed)
    assert "<ul>" in out
    assert out.count("<li>") == 2
    assert "a.lml" in out and "b.lml" in out
    kept = split_adjacent_file_links('<p>见 <a href="/x">附件</a> 说明</p>')
    assert kept.startswith("<p>")


def test_prepare_article_body_skips_markdown() -> None:
    raw = "<script>alert(1)</script>\n\n**hi**"
    assert prepare_article_body(raw, "markdown") == raw
    assert "<script>" not in prepare_article_body(raw, "html")


def test_normalize_cover_url() -> None:
    assert normalize_cover_url("") is None
    assert normalize_cover_url("/uploads/articles/a.png") == "/uploads/articles/a.png"
    assert (
        normalize_cover_url("https://cdn.example/cover.jpg")
        == "https://cdn.example/cover.jpg"
    )
    with pytest.raises(ArticleError) as exc:
        normalize_cover_url("javascript:alert(1)")
    assert exc.value.status_code == 400
    with pytest.raises(ArticleError):
        normalize_cover_url("//evil.example/x")
    with pytest.raises(ArticleError):
        normalize_cover_url("/uploads/../etc/passwd")


def test_create_article_sanitizes_html_body() -> None:
    db = _session()
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    row = articles_svc.create_article(
        db,
        author=author,
        title="HTML post",
        body='<p>safe</p><script>alert(1)</script>',
        body_format=articles_svc.FORMAT_HTML,
    )
    assert "<script>" not in (row.body or "")
    assert "safe" in (row.body or "")
    pictured = articles_svc.create_article(
        db,
        author=author,
        title="with image",
        body='<p><img src="/uploads/articles/halo/a.png" alt="图"></p>',
        body_format=articles_svc.FORMAT_HTML,
    )
    assert "/uploads/articles/halo/a.png" in (pictured.body or "")
    with pytest.raises(ArticleError) as exc:
        articles_svc.create_article(
            db,
            author=author,
            title="bad cover",
            body="x",
            cover_url="javascript:alert(1)",
        )
    assert exc.value.status_code == 400
