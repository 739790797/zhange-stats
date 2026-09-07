"""酒馆文章 CRUD、评论。"""

from __future__ import annotations

import re

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.timeutil import now_naive
from app.models.articles import (
    Article,
    ArticleAuthor,
    ArticleCategory,
    ArticleComment,
    ArticleTag,
    ArticleVersion,
)
from app.models.user import User
from app.services.articles.errors import ArticleError
from app.services.articles.sanitize import normalize_cover_url, prepare_article_body
from app.services.articles.slug import ensure_slug, is_reserved_slug, slugify

STATUS_PUBLISHED = "published"
STATUS_DRAFT = "draft"
FORMAT_MARKDOWN = "markdown"
FORMAT_HTML = "html"
ALLOWED_WRITE_STATUS = frozenset({STATUS_PUBLISHED, STATUS_DRAFT})
ALLOWED_LIST_STATUS = ALLOWED_WRITE_STATUS
ALLOWED_FORMAT = frozenset({FORMAT_MARKDOWN, FORMAT_HTML})
MAX_TITLE = 200
MAX_SUMMARY = 512
MAX_COMMENT = 2000
MAX_BODY = 500_000
MAX_VERSIONS = 100
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_Q = 80
ALLOWED_SORT = frozenset({"latest", "hot"})
_CHIP_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _raise(status: int, message: str) -> None:
    raise ArticleError(status, message)


def is_listed_author(db: Session, user_id: int) -> bool:
    return (
        db.query(ArticleAuthor.user_id)
        .filter(ArticleAuthor.user_id == user_id)
        .first()
        is not None
    )


def can_write(db: Session, user: User) -> bool:
    return bool(user.is_admin_user or is_listed_author(db, user.id))


def can_edit(db: Session, user: User, article: Article) -> bool:
    if user.is_admin_user:
        return True
    return article.author_user_id == user.id and is_listed_author(db, user.id)


def capabilities(db: Session, user: User) -> dict:
    writer = can_write(db, user)
    return {
        "can_write": writer,
        "can_admin": bool(user.is_admin_user),
        "is_author": is_listed_author(db, user.id),
    }


def ensure_can_write(db: Session, user: User) -> None:
    if not can_write(db, user):
        _raise(403, "需要酒馆作者权限")


def ensure_can_edit(db: Session, user: User, article: Article) -> None:
    if not can_edit(db, user, article):
        _raise(403, "只能编辑自己的文章")


def _version_payload(row: Article) -> dict[str, str | None]:
    return {
        "title": row.title,
        "summary": row.summary or "",
        "body": row.body or "",
        "body_format": row.body_format,
        "cover_url": row.cover_url,
    }


def _prune_versions(db: Session, article_id: int) -> None:
    rows = (
        db.query(ArticleVersion)
        .filter(ArticleVersion.article_id == article_id)
        .order_by(ArticleVersion.version_no.asc())
        .all()
    )
    extra = len(rows) - MAX_VERSIONS
    if extra <= 0:
        return
    for old in rows[:extra]:
        db.delete(old)


def append_version_if_changed(
    db: Session,
    row: Article,
    *,
    actor_id: int | None,
    note: str = "",
    force: bool = False,
) -> ArticleVersion | None:
    if row.status != STATUS_PUBLISHED:
        return None
    payload = _version_payload(row)
    last = (
        db.query(ArticleVersion)
        .filter(ArticleVersion.article_id == row.id)
        .order_by(ArticleVersion.version_no.desc())
        .first()
    )
    if (
        not force
        and last is not None
        and last.title == payload["title"]
        and (last.summary or "") == payload["summary"]
        and (last.body or "") == payload["body"]
        and last.body_format == payload["body_format"]
        and last.cover_url == payload["cover_url"]
    ):
        return None
    next_no = (last.version_no + 1) if last else 1
    ver = ArticleVersion(
        article_id=row.id,
        version_no=next_no,
        title=payload["title"] or "",
        summary=payload["summary"] or "",
        body=payload["body"] or "",
        body_format=payload["body_format"] or FORMAT_MARKDOWN,
        cover_url=payload["cover_url"],
        note=(note or "")[:128],
        created_by_user_id=actor_id,
        created_at=now_naive(),
    )
    db.add(ver)
    db.flush()
    _prune_versions(db, row.id)
    return ver


def _unique_slug(db: Session, base: str, *, exclude_id: int | None = None) -> str:
    if is_reserved_slug(base):
        _raise(400, "该短链为系统保留，请换一个")
    slug = base
    n = 2
    while True:
        q = db.query(Article.id).filter(Article.slug == slug)
        if exclude_id is not None:
            q = q.filter(Article.id != exclude_id)
        if q.first() is None:
            return slug
        suffix = f"-{n}"
        slug = f"{base[: 191 - len(suffix)]}{suffix}"
        n += 1


def _load_terms(
    db: Session,
    model: type[ArticleCategory] | type[ArticleTag],
    ids: list[int] | None,
) -> list:
    if not ids:
        return []
    rows = db.query(model).filter(model.id.in_(ids)).all()
    found = {row.id for row in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        _raise(400, "分类或标签不存在")
    return rows


def normalize_chip_color(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if not _CHIP_HEX.fullmatch(raw):
        _raise(400, "芯片颜色须为 #RGB 或 #RRGGBB")
    if len(raw) == 4:
        raw = "#" + "".join(ch * 2 for ch in raw[1:])
    return raw.lower()


def category_to_out(row: ArticleCategory) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "sort_order": row.sort_order,
        "admin_only": bool(row.admin_only),
        "chip_color": row.chip_color or None,
    }


def _assign_categories(
    db: Session,
    ids: list[int] | None,
    *,
    actor: User,
) -> list[ArticleCategory]:
    rows = _load_terms(db, ArticleCategory, ids)
    if actor.is_admin_user:
        return rows
    locked = next((row for row in rows if row.admin_only), None)
    if locked is not None:
        _raise(403, f"分类「{locked.name}」仅管理员可用")
    return rows


def _author_payload(user: User | None) -> dict:
    if user is None:
        return {"user_id": None, "display_name": "已注销", "avatar_url": None}
    member = user.member
    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "avatar_url": member.avatar_url if member else None,
    }


def _comment_author_payload(row: ArticleComment) -> dict:
    if row.user is not None:
        return _author_payload(row.user)
    name = (row.guest_name or "").strip() or "访客"
    return {"user_id": None, "display_name": name, "avatar_url": None}


def article_to_list_item(row: Article, *, comment_count: int = 0) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "summary": row.summary or "",
        "cover_url": row.cover_url,
        "status": row.status,
        "published_at": row.published_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "comment_count": int(comment_count),
        "author": _author_payload(row.author),
        "categories": [category_to_out(c) for c in row.categories],
        "tags": [{"id": t.id, "slug": t.slug, "name": t.name} for t in row.tags],
    }


def article_to_detail(row: Article) -> dict:
    item = article_to_list_item(row, comment_count=len(row.comments))
    item["body"] = row.body or ""
    item["body_format"] = row.body_format
    item["updated_at"] = row.updated_at
    return item


def _comment_counts(db: Session, article_ids: list[int]) -> dict[int, int]:
    if not article_ids:
        return {}
    rows = (
        db.query(ArticleComment.article_id, func.count(ArticleComment.id))
        .filter(ArticleComment.article_id.in_(article_ids))
        .group_by(ArticleComment.article_id)
        .all()
    )
    return {int(article_id): int(n) for article_id, n in rows}


def _items_with_counts(db: Session, rows: list[Article]) -> list[dict]:
    counts = _comment_counts(db, [row.id for row in rows])
    return [
        article_to_list_item(row, comment_count=counts.get(row.id, 0))
        for row in rows
    ]


def _page_out(
    db: Session,
    rows: list[Article],
    *,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    return {
        "items": _items_with_counts(db, rows),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def comment_to_out(row: ArticleComment) -> dict:
    return {
        "id": row.id,
        "body": row.body,
        "parent_id": row.parent_id,
        "created_at": row.created_at,
        "author": _comment_author_payload(row),
    }


def _article_query(db: Session):
    return db.query(Article).options(
        joinedload(Article.author).joinedload(User.member),
        selectinload(Article.categories),
        selectinload(Article.tags),
    )


def list_published(
    db: Session,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    sort: str = "latest",
) -> dict:
    page = max(1, page)
    page_size = min(MAX_PAGE_SIZE, max(1, page_size))
    sort_key = (sort or "latest").strip().lower()
    if sort_key not in ALLOWED_SORT:
        _raise(400, "排序无效")
    query = db.query(Article).filter(Article.status == STATUS_PUBLISHED)
    if category:
        query = query.filter(
            Article.categories.any(ArticleCategory.slug == category)
        )
    if tag:
        query = query.filter(Article.tags.any(ArticleTag.slug == tag))
    needle = (q or "").strip()[:MAX_SEARCH_Q]
    if needle:
        query = query.filter(
            or_(
                Article.title.contains(needle, autoescape=True),
                Article.summary.contains(needle, autoescape=True),
            )
        )
    total = query.count()
    if sort_key == "hot":
        comment_n = (
            db.query(
                ArticleComment.article_id.label("article_id"),
                func.count(ArticleComment.id).label("n"),
            )
            .group_by(ArticleComment.article_id)
            .subquery()
        )
        query = query.outerjoin(comment_n, Article.id == comment_n.c.article_id)
        query = query.order_by(
            func.coalesce(comment_n.c.n, 0).desc(),
            Article.published_at.desc(),
            Article.id.desc(),
        )
    else:
        query = query.order_by(Article.published_at.desc(), Article.id.desc())
    rows = (
        query.options(
            joinedload(Article.author).joinedload(User.member),
            selectinload(Article.categories),
            selectinload(Article.tags),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _page_out(db, rows, total=total, page=page, page_size=page_size)


def list_admin(
    db: Session,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: str | None = None,
) -> dict:
    page = max(1, page)
    page_size = min(MAX_PAGE_SIZE, max(1, page_size))
    q = db.query(Article)
    if status:
        if status not in ALLOWED_LIST_STATUS:
            _raise(400, "状态无效")
        q = q.filter(Article.status == status)
    total = q.count()
    rows = (
        q.options(
            joinedload(Article.author).joinedload(User.member),
            selectinload(Article.categories),
            selectinload(Article.tags),
        )
        .order_by(Article.updated_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _page_out(db, rows, total=total, page=page, page_size=page_size)


def get_published_by_slug(db: Session, slug: str) -> Article:
    row = (
        _article_query(db)
        .filter(Article.slug == slug, Article.status == STATUS_PUBLISHED)
        .first()
    )
    if row is None:
        _raise(404, "文章不存在")
    return row


def get_by_id(db: Session, article_id: int) -> Article:
    row = _article_query(db).filter(Article.id == article_id).first()
    if row is None:
        _raise(404, "文章不存在")
    return row


def _apply_publish_fields(row: Article, status: str) -> None:
    row.status = status
    if status == STATUS_PUBLISHED:
        if row.published_at is None:
            row.published_at = now_naive()
    else:
        row.published_at = row.published_at


def create_article(
    db: Session,
    *,
    author: User,
    title: str,
    body: str,
    slug: str | None = None,
    summary: str = "",
    body_format: str = FORMAT_MARKDOWN,
    cover_url: str | None = None,
    status: str = STATUS_DRAFT,
    category_ids: list[int] | None = None,
    tag_ids: list[int] | None = None,
) -> Article:
    ensure_can_write(db, author)
    title = (title or "").strip()
    if not title:
        _raise(400, "标题不能为空")
    if len(title) > MAX_TITLE:
        _raise(400, "标题过长")
    summary = (summary or "").strip()
    if len(summary) > MAX_SUMMARY:
        _raise(400, "摘要过长")
    body = body or ""
    if len(body) > MAX_BODY:
        _raise(400, "正文过长")
    if body_format not in ALLOWED_FORMAT:
        _raise(400, "正文格式无效")
    if status not in ALLOWED_WRITE_STATUS:
        _raise(400, "状态无效")
    body = prepare_article_body(body, body_format)
    cover = normalize_cover_url(cover_url)
    base = ensure_slug(title, slug)
    unique = _unique_slug(db, base)
    now = now_naive()
    row = Article(
        slug=unique,
        title=title,
        summary=summary,
        body=body,
        body_format=body_format,
        cover_url=cover,
        status=status,
        author_user_id=author.id,
        created_at=now,
        updated_at=now,
    )
    _apply_publish_fields(row, status)
    row.categories = _assign_categories(db, category_ids, actor=author)
    row.tags = _load_terms(db, ArticleTag, tag_ids)
    db.add(row)
    db.flush()
    append_version_if_changed(db, row, actor_id=author.id, force=True)
    db.commit()
    return get_by_id(db, row.id)


def update_article(
    db: Session,
    article_id: int,
    *,
    actor: User,
    title: str | None = None,
    body: str | None = None,
    slug: str | None = None,
    summary: str | None = None,
    body_format: str | None = None,
    cover_url: str | None = None,
    status: str | None = None,
    category_ids: list[int] | None = None,
    tag_ids: list[int] | None = None,
) -> Article:
    row = get_by_id(db, article_id)
    ensure_can_edit(db, actor, row)
    if title is not None:
        title = title.strip()
        if not title:
            _raise(400, "标题不能为空")
        if len(title) > MAX_TITLE:
            _raise(400, "标题过长")
        row.title = title
    if summary is not None:
        summary = summary.strip()
        if len(summary) > MAX_SUMMARY:
            _raise(400, "摘要过长")
        row.summary = summary
    next_format = row.body_format
    if body_format is not None:
        if body_format not in ALLOWED_FORMAT:
            _raise(400, "正文格式无效")
        next_format = body_format
        row.body_format = body_format
    if body is not None:
        if len(body) > MAX_BODY:
            _raise(400, "正文过长")
        row.body = prepare_article_body(body, next_format)
    elif body_format is not None:
        row.body = prepare_article_body(row.body or "", next_format)
    if cover_url is not None:
        row.cover_url = normalize_cover_url(cover_url)
    if slug is not None:
        base = ensure_slug(row.title, slug)
        row.slug = _unique_slug(db, base, exclude_id=row.id)
    if status is not None:
        if status not in ALLOWED_WRITE_STATUS:
            _raise(400, "状态无效")
        _apply_publish_fields(row, status)
    if category_ids is not None:
        row.categories = _assign_categories(db, category_ids, actor=actor)
    if tag_ids is not None:
        row.tags = _load_terms(db, ArticleTag, tag_ids)
    row.updated_at = now_naive()
    db.flush()
    append_version_if_changed(db, row, actor_id=actor.id)
    db.commit()
    return get_by_id(db, row.id)


def delete_article(db: Session, article_id: int, *, actor: User) -> None:
    row = db.query(Article).filter(Article.id == article_id).first()
    if row is None:
        _raise(404, "文章不存在")
    ensure_can_edit(db, actor, row)
    db.delete(row)
    db.commit()


def list_mine(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    status: str | None = None,
) -> dict:
    ensure_can_write(db, user)
    page = max(1, page)
    page_size = min(MAX_PAGE_SIZE, max(1, page_size))
    q = db.query(Article).filter(Article.author_user_id == user.id)
    if status:
        if status not in ALLOWED_LIST_STATUS:
            _raise(400, "状态无效")
        q = q.filter(Article.status == status)
    total = q.count()
    rows = (
        q.options(
            joinedload(Article.author).joinedload(User.member),
            selectinload(Article.categories),
            selectinload(Article.tags),
        )
        .order_by(Article.updated_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _page_out(db, rows, total=total, page=page, page_size=page_size)


def get_for_editor(db: Session, article_id: int, actor: User) -> Article:
    row = get_by_id(db, article_id)
    ensure_can_edit(db, actor, row)
    return row


def _version_to_item(row: ArticleVersion) -> dict:
    return {
        "id": row.id,
        "version_no": row.version_no,
        "title": row.title,
        "summary": row.summary or "",
        "note": row.note or "",
        "created_at": row.created_at,
        "created_by": _author_payload(row.created_by),
    }


def _version_to_detail(row: ArticleVersion) -> dict:
    item = _version_to_item(row)
    item["body"] = row.body or ""
    item["body_format"] = row.body_format
    item["cover_url"] = row.cover_url
    return item


def list_versions(db: Session, article_id: int, actor: User) -> list[dict]:
    article = get_for_editor(db, article_id, actor)
    rows = (
        db.query(ArticleVersion)
        .options(joinedload(ArticleVersion.created_by).joinedload(User.member))
        .filter(ArticleVersion.article_id == article.id)
        .order_by(ArticleVersion.version_no.desc())
        .all()
    )
    return [_version_to_item(r) for r in rows]


def get_version(db: Session, article_id: int, version_id: int, actor: User) -> dict:
    get_for_editor(db, article_id, actor)
    row = (
        db.query(ArticleVersion)
        .options(joinedload(ArticleVersion.created_by).joinedload(User.member))
        .filter(
            ArticleVersion.id == version_id,
            ArticleVersion.article_id == article_id,
        )
        .first()
    )
    if row is None:
        _raise(404, "版本不存在")
    return _version_to_detail(row)


def restore_version(
    db: Session,
    article_id: int,
    version_id: int,
    actor: User,
) -> Article:
    article = get_for_editor(db, article_id, actor)
    ver = (
        db.query(ArticleVersion)
        .filter(
            ArticleVersion.id == version_id,
            ArticleVersion.article_id == article.id,
        )
        .first()
    )
    if ver is None:
        _raise(404, "版本不存在")
    article.title = ver.title
    article.summary = ver.summary or ""
    article.body_format = ver.body_format
    article.body = prepare_article_body(ver.body or "", ver.body_format)
    try:
        article.cover_url = normalize_cover_url(ver.cover_url)
    except ArticleError:
        article.cover_url = None
    article.updated_at = now_naive()
    db.flush()
    append_version_if_changed(
        db,
        article,
        actor_id=actor.id,
        note=f"恢复自第 {ver.version_no} 版",
        force=True,
    )
    db.commit()
    return get_by_id(db, article.id)


def list_authors(db: Session) -> list[dict]:
    rows = (
        db.query(ArticleAuthor)
        .options(joinedload(ArticleAuthor.user).joinedload(User.member))
        .all()
    )
    rows.sort(key=lambda r: (r.user.display_name if r.user else "", r.user_id))
    return [_author_payload(r.user) | {"user_id": r.user_id} for r in rows]


def set_authors(db: Session, user_ids: list[int]) -> list[dict]:
    wanted = []
    seen: set[int] = set()
    for raw in user_ids:
        uid = int(raw)
        if uid in seen:
            continue
        seen.add(uid)
        wanted.append(uid)
    if wanted:
        found = {u.id for u in db.query(User).filter(User.id.in_(wanted)).all()}
        missing = [i for i in wanted if i not in found]
        if missing:
            _raise(400, "用户不存在")
    existing = db.query(ArticleAuthor).all()
    for row in existing:
        if row.user_id not in seen:
            db.delete(row)
    have = {row.user_id for row in existing}
    for uid in wanted:
        if uid not in have:
            db.add(ArticleAuthor(user_id=uid, created_at=now_naive()))
    db.commit()
    return list_authors(db)


def list_categories(db: Session) -> list[dict]:
    rows = (
        db.query(ArticleCategory)
        .order_by(ArticleCategory.sort_order.asc(), ArticleCategory.id.asc())
        .all()
    )
    return [category_to_out(r) for r in rows]


def list_tags(db: Session) -> list[dict]:
    rows = db.query(ArticleTag).order_by(ArticleTag.name.asc()).all()
    return [{"id": r.id, "slug": r.slug, "name": r.name} for r in rows]


def upsert_category(
    db: Session,
    *,
    category_id: int | None = None,
    name: str,
    slug: str | None = None,
    sort_order: int = 0,
    admin_only: bool = False,
    chip_color: str | None = None,
) -> ArticleCategory:
    name = (name or "").strip()
    if not name:
        _raise(400, "分类名不能为空")
    base = ensure_slug(name, slug)
    if is_reserved_slug(base):
        _raise(400, "该短链为系统保留，请换一个")
    color = normalize_chip_color(chip_color)
    q = db.query(ArticleCategory).filter(ArticleCategory.slug == base)
    if category_id is not None:
        q = q.filter(ArticleCategory.id != category_id)
    if q.first():
        _raise(400, "分类短链已存在")
    if category_id is None:
        row = ArticleCategory(
            name=name,
            slug=base,
            sort_order=sort_order,
            admin_only=bool(admin_only),
            chip_color=color,
            created_at=now_naive(),
        )
        db.add(row)
    else:
        row = db.query(ArticleCategory).filter(ArticleCategory.id == category_id).first()
        if row is None:
            _raise(404, "分类不存在")
        row.name = name
        row.slug = base
        row.sort_order = sort_order
        row.admin_only = bool(admin_only)
        row.chip_color = color
    db.commit()
    db.refresh(row)
    return row


def delete_category(db: Session, category_id: int) -> None:
    row = db.query(ArticleCategory).filter(ArticleCategory.id == category_id).first()
    if row is None:
        _raise(404, "分类不存在")
    db.delete(row)
    db.commit()


def upsert_tag(
    db: Session,
    *,
    tag_id: int | None = None,
    name: str,
    slug: str | None = None,
) -> ArticleTag:
    name = (name or "").strip()
    if not name:
        _raise(400, "标签名不能为空")
    base = ensure_slug(name, slug)
    q = db.query(ArticleTag).filter(ArticleTag.slug == base)
    if tag_id is not None:
        q = q.filter(ArticleTag.id != tag_id)
    if q.first():
        _raise(400, "标签短链已存在")
    if tag_id is None:
        row = ArticleTag(name=name, slug=base)
        db.add(row)
    else:
        row = db.query(ArticleTag).filter(ArticleTag.id == tag_id).first()
        if row is None:
            _raise(404, "标签不存在")
        row.name = name
        row.slug = base
    db.commit()
    db.refresh(row)
    return row


def delete_tag(db: Session, tag_id: int) -> None:
    row = db.query(ArticleTag).filter(ArticleTag.id == tag_id).first()
    if row is None:
        _raise(404, "标签不存在")
    db.delete(row)
    db.commit()


def list_comments(db: Session, slug: str) -> list[dict]:
    article = get_published_by_slug(db, slug)
    rows = (
        db.query(ArticleComment)
        .options(joinedload(ArticleComment.user).joinedload(User.member))
        .filter(ArticleComment.article_id == article.id)
        .order_by(ArticleComment.created_at.asc(), ArticleComment.id.asc())
        .all()
    )
    return [comment_to_out(r) for r in rows]


def add_comment(
    db: Session,
    slug: str,
    *,
    user: User,
    body: str,
    parent_id: int | None = None,
) -> ArticleComment:
    article = get_published_by_slug(db, slug)
    text = (body or "").strip()
    if not text:
        _raise(400, "评论不能为空")
    if len(text) > MAX_COMMENT:
        _raise(400, "评论过长")
    parent: ArticleComment | None = None
    if parent_id is not None:
        parent = (
            db.query(ArticleComment)
            .filter(
                ArticleComment.id == parent_id,
                ArticleComment.article_id == article.id,
            )
            .first()
        )
        if parent is None:
            _raise(400, "回复的评论不存在")
        if parent.parent_id is not None:
            _raise(400, "只支持一层回复")
    row = ArticleComment(
        article_id=article.id,
        user_id=user.id,
        body=text,
        parent_id=parent.id if parent else None,
        created_at=now_naive(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row = (
        db.query(ArticleComment)
        .options(joinedload(ArticleComment.user).joinedload(User.member))
        .filter(ArticleComment.id == row.id)
        .one()
    )
    return row


def delete_comment(db: Session, comment_id: int) -> None:
    row = db.query(ArticleComment).filter(ArticleComment.id == comment_id).first()
    if row is None:
        _raise(404, "评论不存在")
    db.delete(row)
    db.commit()


def ensure_category_by_slug(db: Session, *, name: str, slug: str) -> ArticleCategory:
    slug = slugify(slug) or slugify(name) or "cat"
    row = db.query(ArticleCategory).filter(ArticleCategory.slug == slug).first()
    if row:
        return row
    row = ArticleCategory(
        name=name.strip() or slug,
        slug=slug,
        sort_order=0,
        admin_only=False,
        chip_color=None,
        created_at=now_naive(),
    )
    db.add(row)
    db.flush()
    return row


def ensure_tag_by_slug(db: Session, *, name: str, slug: str) -> ArticleTag:
    slug = slugify(slug) or slugify(name) or "tag"
    row = db.query(ArticleTag).filter(ArticleTag.slug == slug).first()
    if row:
        return row
    row = ArticleTag(name=name.strip() or slug, slug=slug, created_at=now_naive())
    db.add(row)
    db.flush()
    return row
