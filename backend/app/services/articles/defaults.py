"""酒馆开发库分类夹具。

仅供 ``python -m local_dev.seed_tavern`` / ``ensure_dev_sample_articles``。
启动与生产更新不得调用：站点分类由管理员在后台维护。
"""

from __future__ import annotations

from typing import NamedTuple

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.articles import ArticleCategory, article_category_links


class DefaultCategory(NamedTuple):
    slug: str
    name: str
    sort_order: int
    admin_only: bool = False
    chip_color: str | None = None


# 本地空库灌数用；不要当成站点分类的权威清单。
DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    DefaultCategory("notice", "站点公告", 10, True, "#c41d7f"),
    DefaultCategory("guides", "游戏攻略", 20, False, "#1677ff"),
    DefaultCategory("tech", "技术分享", 30, False, "#722ed1"),
    DefaultCategory("raid", "联机开黑", 40, False, "#d46b08"),
    DefaultCategory("casual", "闲聊随笔", 50, False, "#389e0d"),
    DefaultCategory("circle", "圈子动态", 60, False, "#13c2c2"),
)

_RENAME_IF = {
    "notice": "公告",
}

_LEGACY_EMPTY = (
    ("news", "资讯"),
    ("share", "分享"),
)


def drop_legacy_empty_categories(db: Session) -> None:
    """清掉开发种子留下的空分类（资讯 / 分享），有文章的不动。"""
    for slug, name in _LEGACY_EMPTY:
        row = (
            db.query(ArticleCategory)
            .filter(ArticleCategory.slug == slug, ArticleCategory.name == name)
            .first()
        )
        if row is None:
            continue
        linked = (
            db.query(article_category_links.c.article_id)
            .filter(article_category_links.c.category_id == row.id)
            .first()
        )
        if linked is not None:
            continue
        db.delete(row)
    db.commit()


def ensure_default_categories(db: Session) -> dict[str, ArticleCategory]:
    """按 slug 补齐开发夹具分类；已有同 slug 不改名称 / 颜色 / 权限。"""
    found: dict[str, ArticleCategory] = {}
    for spec in DEFAULT_CATEGORIES:
        row = db.query(ArticleCategory).filter(ArticleCategory.slug == spec.slug).first()
        if row is None:
            row = ArticleCategory(
                slug=spec.slug,
                name=spec.name,
                sort_order=spec.sort_order,
                admin_only=spec.admin_only,
                chip_color=spec.chip_color,
                created_at=now_naive(),
            )
            db.add(row)
            db.flush()
        elif spec.slug in _RENAME_IF and row.name == _RENAME_IF[spec.slug]:
            row.name = spec.name
            if row.sort_order == 0:
                row.sort_order = spec.sort_order
        found[spec.slug] = row
    db.commit()
    drop_legacy_empty_categories(db)
    return found
