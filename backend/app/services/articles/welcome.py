"""战鸽酒馆默认欢迎文。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.articles import Article
from app.models.user import User, UserRole
from app.services.articles import service as articles_svc

WELCOME_SLUG = "welcome"
WELCOME_TITLE = "欢迎来到战鸽酒馆"
WELCOME_SUMMARY = "坐下喝一杯。这里收着圈子里的文章与随笔，欢迎阅读和评论。"
WELCOME_BODY = """战鸽酒馆是圈子的公开文章角：攻略、随笔、闲聊都可以放在这里。未登录也能读已发布的稿；登录后可以留言。

被管理员标成作者的成员，可以在酒馆页写文章、改自己的稿。删除是收回大厅展示，并不是从库里抹掉。

## 怎么读

大厅左侧是文章列表，可按最新/热门、分类和标题搜索。右侧「重点关注」和「最新文章」方便跳转。点标题或「详情」进正文。

## 怎么写

有作者权限时，标题右侧会出现「写文章」。草稿只在「我的文稿」里，发布后才会出现在大厅。

先看完这篇，再决定要不要下一篇。坐下慢慢看就好。
"""


def ensure_welcome_article(db: Session) -> Article | None:
    """已有同 slug 则不动；没有管理员则跳过。启动时幂等调用。"""
    existing = db.query(Article).filter(Article.slug == WELCOME_SLUG).first()
    if existing is not None:
        return existing
    admin = (
        db.query(User)
        .filter(User.role == UserRole.admin)
        .order_by(User.id.asc())
        .first()
    )
    if admin is None:
        return None
    return articles_svc.create_article(
        db,
        author=admin,
        title=WELCOME_TITLE,
        body=WELCOME_BODY,
        slug=WELCOME_SLUG,
        summary=WELCOME_SUMMARY,
        status=articles_svc.STATUS_PUBLISHED,
    )
