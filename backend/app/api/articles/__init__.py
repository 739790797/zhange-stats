"""战鸽酒馆文章 API。"""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.articles.schemas import (
    ArticleAssetOut,
    ArticleAuthorOut,
    ArticleAuthorsPutIn,
    ArticleCapabilityOut,
    ArticleCategoryOut,
    ArticleCategoryWriteIn,
    ArticleCommentCreateIn,
    ArticleCommentOut,
    ArticleDetailOut,
    ArticleListOut,
    ArticleMathRecognizeOut,
    ArticlePatchIn,
    ArticleTermOut,
    ArticleTagWriteIn,
    ArticleVersionDetailOut,
    ArticleVersionListItemOut,
    ArticleWriteIn,
)
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.core.rate_limit import client_ip, platform_limiter
from app.models.user import User
from app.services.articles import service as articles_svc
from app.services.articles.errors import ArticleError
from app.services.articles.store import save_article_asset
from app.services.articles.texteller import MAX_RECOGNIZE_BYTES, recognize_image_bytes

router = APIRouter(
    prefix="/articles",
    tags=["articles"],
    dependencies=[Depends(require_feature("tavern"))],
)


def _raise(exc: ArticleError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _hit_article_write_limit(request: Request, user: User) -> None:
    ip = client_ip(request)
    platform_limiter.hit(f"articles-write:ip:{ip}", limit=40, window_sec=600)
    platform_limiter.hit(f"articles-write:uid:{user.id}", limit=20, window_sec=600)


def require_tavern_writer(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    try:
        articles_svc.ensure_can_write(db, user)
    except ArticleError as exc:
        _raise(exc)
    return user


@router.get("", response_model=ArticleListOut)
def list_articles(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=80),
    sort: str = Query(default="latest"),
) -> dict:
    try:
        return articles_svc.list_published(
            db,
            page=page,
            page_size=page_size,
            category=category,
            tag=tag,
            q=q,
            sort=sort,
        )
    except ArticleError as exc:
        _raise(exc)


@router.get("/admin", response_model=ArticleListOut)
def list_articles_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status: str | None = Query(default=None),
) -> dict:
    try:
        return articles_svc.list_admin(db, page=page, page_size=page_size, status=status)
    except ArticleError as exc:
        _raise(exc)


@router.get("/capabilities", response_model=ArticleCapabilityOut)
def get_capabilities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return articles_svc.capabilities(db, user)


@router.get("/mine", response_model=ArticleListOut)
def list_my_articles(
    db: Session = Depends(get_db),
    user: User = Depends(require_tavern_writer),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status: str | None = Query(default=None),
) -> dict:
    try:
        return articles_svc.list_mine(
            db, user, page=page, page_size=page_size, status=status
        )
    except ArticleError as exc:
        _raise(exc)


@router.get("/authors", response_model=list[ArticleAuthorOut])
def get_authors(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    return articles_svc.list_authors(db)


@router.put("/authors", response_model=list[ArticleAuthorOut])
def put_authors(
    body: ArticleAuthorsPutIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    try:
        return articles_svc.set_authors(db, body.user_ids)
    except ArticleError as exc:
        _raise(exc)


@router.get("/categories", response_model=list[ArticleCategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[dict]:
    return articles_svc.list_categories(db)


@router.post("/categories", response_model=ArticleCategoryOut)
def create_category(
    body: ArticleCategoryWriteIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ArticleCategoryOut:
    try:
        row = articles_svc.upsert_category(
            db,
            name=body.name,
            slug=body.slug,
            sort_order=body.sort_order,
            admin_only=body.admin_only,
            chip_color=body.chip_color,
        )
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.category_to_out(row)


@router.patch("/categories/{category_id}", response_model=ArticleCategoryOut)
def patch_category(
    category_id: int,
    body: ArticleCategoryWriteIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ArticleCategoryOut:
    try:
        row = articles_svc.upsert_category(
            db,
            category_id=category_id,
            name=body.name,
            slug=body.slug,
            sort_order=body.sort_order,
            admin_only=body.admin_only,
            chip_color=body.chip_color,
        )
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.category_to_out(row)


@router.delete("/categories/{category_id}", status_code=204)
def remove_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    try:
        articles_svc.delete_category(db, category_id)
    except ArticleError as exc:
        _raise(exc)


@router.get("/tags", response_model=list[ArticleTermOut])
def list_tags(db: Session = Depends(get_db)) -> list[dict]:
    return articles_svc.list_tags(db)


@router.post("/tags", response_model=ArticleTermOut)
def create_tag(
    body: ArticleTagWriteIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ArticleTermOut:
    try:
        row = articles_svc.upsert_tag(db, name=body.name, slug=body.slug)
    except ArticleError as exc:
        _raise(exc)
    return ArticleTermOut(id=row.id, slug=row.slug, name=row.name)


@router.patch("/tags/{tag_id}", response_model=ArticleTermOut)
def patch_tag(
    tag_id: int,
    body: ArticleTagWriteIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ArticleTermOut:
    try:
        row = articles_svc.upsert_tag(db, tag_id=tag_id, name=body.name, slug=body.slug)
    except ArticleError as exc:
        _raise(exc)
    return ArticleTermOut(id=row.id, slug=row.slug, name=row.name)


@router.delete("/tags/{tag_id}", status_code=204)
def remove_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    try:
        articles_svc.delete_tag(db, tag_id)
    except ArticleError as exc:
        _raise(exc)


@router.post("/math/recognize", response_model=ArticleMathRecognizeOut)
async def recognize_math(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_tavern_writer),
) -> ArticleMathRecognizeOut:
    ip = client_ip(request)
    platform_limiter.hit(f"articles-math:ip:{ip}", limit=10, window_sec=600)
    platform_limiter.hit(f"articles-math:uid:{user.id}", limit=6, window_sec=600)
    raw = await file.read(MAX_RECOGNIZE_BYTES + 1)
    try:
        return ArticleMathRecognizeOut(latex=recognize_image_bytes(raw))
    except ArticleError as exc:
        _raise(exc)


@router.post("/assets", response_model=ArticleAssetOut)
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_tavern_writer),
) -> ArticleAssetOut:
    _hit_article_write_limit(request, user)
    stored = await save_article_asset(file, db=db, owner_user_id=user.id)
    return ArticleAssetOut(url=stored.url, serial=stored.serial)


@router.post("", response_model=ArticleDetailOut)
def create_article(
    body: ArticleWriteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_tavern_writer),
) -> dict:
    _hit_article_write_limit(request, user)
    try:
        row = articles_svc.create_article(
            db,
            author=user,
            title=body.title,
            body=body.body,
            slug=body.slug,
            summary=body.summary,
            body_format=body.body_format,
            cover_url=body.cover_url,
            status=body.status,
            category_ids=body.category_ids,
            tag_ids=body.tag_ids,
        )
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.article_to_detail(row)


@router.get("/id/{article_id}", response_model=ArticleDetailOut)
def get_article_editor(
    article_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        row = articles_svc.get_for_editor(db, article_id, user)
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.article_to_detail(row)


@router.patch("/id/{article_id}", response_model=ArticleDetailOut)
def patch_article(
    article_id: int,
    body: ArticlePatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_tavern_writer),
) -> dict:
    _hit_article_write_limit(request, user)
    try:
        row = articles_svc.update_article(
            db,
            article_id,
            actor=user,
            **body.model_dump(exclude_unset=True),
        )
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.article_to_detail(row)


@router.delete("/id/{article_id}", status_code=204)
def remove_article(
    article_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_tavern_writer),
) -> None:
    try:
        articles_svc.delete_article(db, article_id, actor=user)
    except ArticleError as exc:
        _raise(exc)


@router.get("/id/{article_id}/versions", response_model=list[ArticleVersionListItemOut])
def get_article_versions(
    article_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    try:
        return articles_svc.list_versions(db, article_id, user)
    except ArticleError as exc:
        _raise(exc)


@router.get(
    "/id/{article_id}/versions/{version_id}",
    response_model=ArticleVersionDetailOut,
)
def get_article_version(
    article_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return articles_svc.get_version(db, article_id, version_id, user)
    except ArticleError as exc:
        _raise(exc)


@router.post(
    "/id/{article_id}/versions/{version_id}/restore",
    response_model=ArticleDetailOut,
)
def restore_article_version(
    article_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_tavern_writer),
) -> dict:
    try:
        row = articles_svc.restore_version(db, article_id, version_id, user)
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.article_to_detail(row)


@router.get("/{slug}", response_model=ArticleDetailOut)
def get_article(slug: str, db: Session = Depends(get_db)) -> dict:
    try:
        row = articles_svc.get_published_by_slug(db, slug)
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.article_to_detail(row)


@router.get("/{slug}/comments", response_model=list[ArticleCommentOut])
def get_comments(slug: str, db: Session = Depends(get_db)) -> list[dict]:
    try:
        return articles_svc.list_comments(db, slug)
    except ArticleError as exc:
        _raise(exc)


@router.post("/{slug}/comments", response_model=ArticleCommentOut)
def post_comment(
    slug: str,
    body: ArticleCommentCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ip = client_ip(request)
    platform_limiter.hit(f"articles-comment:ip:{ip}", limit=20, window_sec=600)
    platform_limiter.hit(f"articles-comment:uid:{user.id}", limit=10, window_sec=600)
    try:
        row = articles_svc.add_comment(
            db, slug, user=user, body=body.body, parent_id=body.parent_id
        )
    except ArticleError as exc:
        _raise(exc)
    return articles_svc.comment_to_out(row)


@router.delete("/{slug}/comments/{comment_id}", status_code=204)
def remove_comment(
    slug: str,
    comment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    try:
        articles_svc.get_published_by_slug(db, slug)
        articles_svc.delete_comment(db, comment_id)
    except ArticleError as exc:
        _raise(exc)
