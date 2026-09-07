"""HTML 入库消毒与封面 URL。"""

from __future__ import annotations

import pytest

from app.services.articles.errors import ArticleError
from app.services.articles.sanitize import (
    normalize_cover_url,
    prepare_article_body,
    sanitize_html,
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
    with pytest.raises(ArticleError) as exc:
        articles_svc.create_article(
            db,
            author=author,
            title="bad cover",
            body="x",
            cover_url="javascript:alert(1)",
        )
    assert exc.value.status_code == 400
