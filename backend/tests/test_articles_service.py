"""酒馆作者权限、物理删除、版本恢复。"""

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


def test_listed_author_create_publish_and_hard_delete() -> None:
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
    article_id = row.id
    assert row.status == articles_svc.STATUS_PUBLISHED
    pub = articles_svc.list_published(db)
    assert pub["total"] == 1
    articles_svc.delete_article(db, article_id, actor=author)
    db.expire_all()
    gone = articles_svc.list_published(db)
    assert gone["total"] == 0
    listed = articles_svc.list_admin(db)
    assert listed["total"] == 0
    assert db.query(Article).filter(Article.id == article_id).first() is None
    with pytest.raises(ArticleError) as exc:
        articles_svc.list_admin(db, status="deleted")
    assert exc.value.status_code == 400
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


def test_draft_has_no_versions_until_publish() -> None:
    db = _session()
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    row = articles_svc.create_article(db, author=author, title="T1", body="body-1")
    assert row.status == articles_svc.STATUS_DRAFT
    assert articles_svc.list_versions(db, row.id, author) == []
    articles_svc.update_article(db, row.id, actor=author, title="T2", body="body-2")
    assert articles_svc.list_versions(db, row.id, author) == []
    published = articles_svc.update_article(
        db,
        row.id,
        actor=author,
        status=articles_svc.STATUS_PUBLISHED,
    )
    vers = articles_svc.list_versions(db, published.id, author)
    assert [v["version_no"] for v in vers] == [1]
    assert vers[0]["title"] == "T2"
    articles_svc.update_article(db, published.id, actor=author, body="body-3")
    assert [v["version_no"] for v in articles_svc.list_versions(db, published.id, author)] == [
        2,
        1,
    ]
    articles_svc.update_article(
        db, published.id, actor=author, status=articles_svc.STATUS_DRAFT
    )
    assert [v["version_no"] for v in articles_svc.list_versions(db, published.id, author)] == [
        2,
        1,
    ]


def test_restore_version() -> None:
    db = _session()
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    row = articles_svc.create_article(
        db,
        author=author,
        title="T1",
        body="body-1",
        status=articles_svc.STATUS_PUBLISHED,
    )
    articles_svc.update_article(db, row.id, actor=author, title="T2", body="body-2")
    vers = articles_svc.list_versions(db, row.id, author)
    assert [v["version_no"] for v in vers] == [2, 1]
    first_id = next(v["id"] for v in vers if v["version_no"] == 1)
    restored = articles_svc.restore_version(db, row.id, first_id, author)
    assert restored.status == articles_svc.STATUS_PUBLISHED
    assert restored.title == "T1"
    assert restored.body == "body-1"
    assert [v["version_no"] for v in articles_svc.list_versions(db, row.id, author)] == [
        3,
        2,
        1,
    ]


def test_deleted_article_is_gone() -> None:
    db = _session()
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    row = articles_svc.create_article(db, author=author, title="Draft", body="x")
    article_id = row.id
    articles_svc.delete_article(db, article_id, actor=author)
    assert db.query(Article).filter(Article.id == article_id).first() is None
    with pytest.raises(ArticleError) as exc:
        articles_svc.update_article(db, article_id, actor=author, title="Nope")
    assert exc.value.status_code == 404


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
    assert set(first) == {spec.slug for spec in DEFAULT_CATEGORIES}
    assert db.query(ArticleCategory).count() == len(DEFAULT_CATEGORIES)
    notice = first["notice"]
    assert notice.admin_only is True
    assert notice.chip_color == "#c41d7f"
    assert first["guides"].admin_only is False
    ensure_default_categories(db)
    assert db.query(ArticleCategory).count() == len(DEFAULT_CATEGORIES)


def test_normalize_chip_color() -> None:
    assert articles_svc.normalize_chip_color(None) is None
    assert articles_svc.normalize_chip_color("  ") is None
    assert articles_svc.normalize_chip_color("#C41") == "#cc4411"
    assert articles_svc.normalize_chip_color("#C41D7F") == "#c41d7f"
    with pytest.raises(ArticleError) as exc:
        articles_svc.normalize_chip_color("red")
    assert exc.value.status_code == 400


def test_author_cannot_assign_admin_only_category() -> None:
    from app.services.articles.defaults import ensure_default_categories

    db = _session()
    admin = _user(db, "root", admin=True)
    author = _user(db, "ann")
    articles_svc.set_authors(db, [author.id])
    cats = ensure_default_categories(db)
    notice_id = cats["notice"].id
    guides_id = cats["guides"].id
    with pytest.raises(ArticleError) as exc:
        articles_svc.create_article(
            db,
            author=author,
            title="Oops",
            body="x",
            category_ids=[notice_id],
        )
    assert exc.value.status_code == 403
    posted = articles_svc.create_article(
        db,
        author=admin,
        title="站点公告",
        body="x",
        category_ids=[notice_id],
    )
    assert [row.slug for row in posted.categories] == ["notice"]
    listed = articles_svc.article_to_list_item(posted)
    assert listed["categories"][0]["admin_only"] is True
    assert listed["categories"][0]["chip_color"] == "#c41d7f"
    row = articles_svc.create_article(
        db, author=author, title="攻略", body="x", category_ids=[guides_id]
    )
    with pytest.raises(ArticleError) as exc:
        articles_svc.update_article(
            db, row.id, actor=author, category_ids=[notice_id]
        )
    assert exc.value.status_code == 403


def test_upsert_category_admin_only_and_chip() -> None:
    db = _session()
    row = articles_svc.upsert_category(
        db,
        name="内部",
        slug="internal",
        admin_only=True,
        chip_color="#C41D7F",
    )
    assert row.admin_only is True
    assert row.chip_color == "#c41d7f"
    listed = articles_svc.list_categories(db)
    assert listed[0]["admin_only"] is True
    assert listed[0]["chip_color"] == "#c41d7f"
    cleared = articles_svc.upsert_category(
        db,
        category_id=row.id,
        name="内部",
        slug="internal",
        admin_only=False,
        chip_color="",
    )
    assert cleared.admin_only is False
    assert cleared.chip_color is None
