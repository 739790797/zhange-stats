"""战鸽酒馆 API DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ArticleAuthorOut(BaseModel):
    user_id: int | None = None
    display_name: str
    avatar_url: str | None = None


class ArticleTermOut(BaseModel):
    id: int
    slug: str
    name: str


class ArticleCategoryOut(ArticleTermOut):
    sort_order: int = 0
    admin_only: bool = False
    chip_color: str | None = None


class ArticleListItemOut(BaseModel):
    id: int
    slug: str
    title: str
    summary: str = ""
    cover_url: str | None = None
    status: str
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    comment_count: int = 0
    author: ArticleAuthorOut
    categories: list[ArticleCategoryOut] = Field(default_factory=list)
    tags: list[ArticleTermOut] = Field(default_factory=list)


class ArticleDetailOut(ArticleListItemOut):
    body: str = ""
    body_format: str = "markdown"
    updated_at: datetime


class ArticleListOut(BaseModel):
    items: list[ArticleListItemOut]
    total: int
    page: int
    page_size: int


class ArticleCapabilityOut(BaseModel):
    can_write: bool
    can_admin: bool
    is_author: bool = False


class ArticleAuthorsPutIn(BaseModel):
    user_ids: list[int] = Field(default_factory=list)


class ArticleVersionListItemOut(BaseModel):
    id: int
    version_no: int
    title: str
    summary: str = ""
    note: str = ""
    created_at: datetime
    created_by: ArticleAuthorOut


class ArticleVersionDetailOut(ArticleVersionListItemOut):
    body: str = ""
    body_format: str = "markdown"
    cover_url: str | None = None


class ArticleWriteIn(BaseModel):
    title: str
    body: str = ""
    slug: str | None = None
    summary: str = ""
    body_format: str = "markdown"
    cover_url: str | None = None
    status: str = "draft"
    category_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)


class ArticlePatchIn(BaseModel):
    title: str | None = None
    body: str | None = None
    slug: str | None = None
    summary: str | None = None
    body_format: str | None = None
    cover_url: str | None = None
    status: str | None = None
    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None


class ArticleAssetOut(BaseModel):
    url: str


class ArticleMathRecognizeOut(BaseModel):
    latex: str


class ArticleCommentOut(BaseModel):
    id: int
    body: str
    parent_id: int | None = None
    created_at: datetime
    author: ArticleAuthorOut


class ArticleCommentCreateIn(BaseModel):
    body: str
    parent_id: int | None = None


class ArticleCategoryWriteIn(BaseModel):
    name: str
    slug: str | None = None
    sort_order: int = 0
    admin_only: bool = False
    chip_color: str | None = None


class ArticleTagWriteIn(BaseModel):
    name: str
    slug: str | None = None
