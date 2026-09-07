"""酒馆作者权限、软删除、版本恢复。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.articles import Article
from app.models.user import User, UserRole
from app.services.articles import service as articles_svc
from app.services.articles.errors import ArticleError


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, username: str, *, admin: bool = False) -> User:
    row = User(
        username=username,
        display_name=username,
        password_hash="x",
        role=UserRole.admin if admin else UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def test_non_author_cannot_create() -> None:
    db = _session()
    user = _user(db, "bob")
    with pytest.raises(ArticleError) as exc:
        articles_svc.create_article(db, author=user, title="Hello", body="x")
    assert exc.value.status_code == 403


def test_listed_author_create_publish_and_soft_delete() -> None:
    db = _session()
    admin = _user(db, "admin", admin=True)
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    row = articles_svc.create_article(
        db,
        author=author,
        title="Raid notes",
        body="v1",
        status=articles_svc.STATUS_PUBLISHED,
    )
    assert row.status == articles_svc.STATUS_PUBLISHED
    pub = articles_svc.list_published(db)
    assert pub["total"] == 1
    articles_svc.delete_article(db, row.id, actor=author)
    db.expire_all()
    gone = articles_svc.list_published(db)
    assert gone["total"] == 0
    listed = articles_svc.list_admin(db)
    assert listed["total"] == 1
    assert listed["items"][0]["status"] == articles_svc.STATUS_DELETED
    still = db.query(Article).filter(Article.id == row.id).one()
    assert still.status == articles_svc.STATUS_DELETED
    admin_list = articles_svc.list_admin(db, status=articles_svc.STATUS_DELETED)
    assert admin_list["total"] == 1
    assert admin.is_admin_user


def test_author_cannot_edit_others() -> None:
    db = _session()
    a = _user(db, "a")
    b = _user(db, "b")
    articles_svc.set_authors(db, [a.id, b.id])
    row = articles_svc.create_article(db, author=a, title="My post", body="x")
    with pytest.raises(ArticleError) as exc:
        articles_svc.update_article(db, row.id, actor=b, title="Stolen")
    assert exc.value.status_code == 403


def test_restore_version_and_undelete() -> None:
    db = _session()
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    row = articles_svc.create_article(db, author=author, title="T1", body="body-1")
    articles_svc.update_article(db, row.id, actor=author, title="T2", body="body-2")
    vers = articles_svc.list_versions(db, row.id, author)
    assert [v["version_no"] for v in vers] == [2, 1]
    first_id = next(v["id"] for v in vers if v["version_no"] == 1)
    articles_svc.delete_article(db, row.id, actor=author)
    restored = articles_svc.restore_version(db, row.id, first_id, author)
    assert restored.status == articles_svc.STATUS_DRAFT
    assert restored.title == "T1"
    assert restored.body == "body-1"


def test_admin_can_write_without_author_row() -> None:
    db = _session()
    admin = _user(db, "root", admin=True)
    row = articles_svc.create_article(db, author=admin, title="Ops", body="ok")
    assert row.author_user_id == admin.id
    caps = articles_svc.capabilities(db, admin)
    assert caps["can_write"] is True
    assert caps["can_admin"] is True
    assert caps["is_author"] is False


def test_welcome_article_seeded_once() -> None:
    from app.services.articles.welcome import WELCOME_SLUG, ensure_welcome_article

    db = _session()
    assert ensure_welcome_article(db) is None
    _user(db, "root", admin=True)
    first = ensure_welcome_article(db)
    assert first is not None
    assert first.slug == WELCOME_SLUG
    assert first.status == articles_svc.STATUS_PUBLISHED
    assert "战鸽酒馆" in first.title
    again = ensure_welcome_article(db)
    assert again is not None and again.id == first.id
    assert db.query(Article).count() == 1


def test_list_published_search_hot_and_comment_count() -> None:
    db = _session()
    author = _user(db, "ann")
    reader = _user(db, "reader")
    articles_svc.set_authors(db, [author.id])
    quiet = articles_svc.create_article(
        db,
        author=author,
        title="Quiet night",
        summary="nothing here",
        body="x",
        status=articles_svc.STATUS_PUBLISHED,
    )
    hot = articles_svc.create_article(
        db,
        author=author,
        title="Raid notes",
        summary="bring extra keys",
        body="y",
        status=articles_svc.STATUS_PUBLISHED,
    )
    articles_svc.add_comment(db, hot.slug, user=reader, body="nice")
    articles_svc.add_comment(db, hot.slug, user=author, body="thanks")

    latest = articles_svc.list_published(db, sort="latest")
    assert [row["title"] for row in latest["items"]] == ["Raid notes", "Quiet night"]
    by_id = {row["id"]: row["comment_count"] for row in latest["items"]}
    assert by_id[hot.id] == 2
    assert by_id[quiet.id] == 0

    ranked = articles_svc.list_published(db, sort="hot")
    assert [row["title"] for row in ranked["items"]] == ["Raid notes", "Quiet night"]

    found = articles_svc.list_published(db, q="Raid")
    assert found["total"] == 1
    assert found["items"][0]["id"] == hot.id

    none = articles_svc.list_published(db, q="no-such-title")
    assert none["total"] == 0

    with pytest.raises(ArticleError) as exc:
        articles_svc.list_published(db, sort="views")
    assert exc.value.status_code == 400


def test_dev_sample_articles_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    from app.models.articles import ArticleCategory
    from app.services.articles.dev_samples import ensure_dev_sample_articles

    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    db = _session()
    assert ensure_dev_sample_articles(db)["skipped"] == "no-admin"
    _user(db, "root", admin=True)
    first = ensure_dev_sample_articles(db)
    assert first["skipped"] is None
    assert first["created"] >= 7
    names = {row.name for row in db.query(ArticleCategory).all()}
    assert {
        "站点公告",
        "游戏攻略",
        "技术分享",
        "联机开黑",
        "闲聊随笔",
        "圈子动态",
    } <= names
    published = articles_svc.list_published(db, page_size=50)
    assert published["total"] >= 8
    titles = {row["title"] for row in published["items"]}
    assert "欢迎来到战鸽酒馆" in titles
    assert "当满月遇上英仙座流星雨" in titles
    again = ensure_dev_sample_articles(db)
    assert again["created"] == 0
    assert articles_svc.list_published(db, page_size=50)["total"] == published["total"]


def test_default_categories_idempotent() -> None:
    from app.models.articles import ArticleCategory
    from app.services.articles.defaults import (
        DEFAULT_CATEGORIES,
        ensure_default_categories,
    )

    db = _session()
    first = ensure_default_categories(db)
    assert set(first) == {slug for slug, _, _ in DEFAULT_CATEGORIES}
    assert db.query(ArticleCategory).count() == len(DEFAULT_CATEGORIES)
    ensure_default_categories(db)
    assert db.query(ArticleCategory).count() == len(DEFAULT_CATEGORIES)
