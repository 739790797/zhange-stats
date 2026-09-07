"""酒馆默认分类（站点级，幂等）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.articles import ArticleCategory, article_category_links

# 适合战鸽数据：公告、攻略、技术、开黑、闲聊、圈子。
DEFAULT_CATEGORIES: tuple[tuple[str, str, int], ...] = (
    ("notice", "站点公告", 10),
    ("guides", "游戏攻略", 20),
    ("tech", "技术分享", 30),
    ("raid", "联机开黑", 40),
    ("casual", "闲聊随笔", 50),
    ("circle", "圈子动态", 60),
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
    """按 slug 补齐默认分类；已有同 slug 不改管理员自定义名（旧「公告」除外）。"""
    found: dict[str, ArticleCategory] = {}
    for slug, name, sort_order in DEFAULT_CATEGORIES:
        row = db.query(ArticleCategory).filter(ArticleCategory.slug == slug).first()
        if row is None:
            row = ArticleCategory(
                slug=slug,
                name=name,
                sort_order=sort_order,
                created_at=now_naive(),
            )
            db.add(row)
            db.flush()
        elif slug in _RENAME_IF and row.name == _RENAME_IF[slug]:
            row.name = name
            if row.sort_order == 0:
                row.sort_order = sort_order
        found[slug] = row
    db.commit()
    drop_legacy_empty_categories(db)
    return found
