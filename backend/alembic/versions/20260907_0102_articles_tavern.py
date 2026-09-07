"""Add tavern article tables.

Revision ID: 20260907_0102
Revises: 20260907_0101
Create Date: 2026-09-07

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0102"
down_revision: Union[str, Sequence[str], None] = "20260907_0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "article_categories" not in tables:
        op.create_table(
            "article_categories",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=191), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )

    if "article_tags" not in tables:
        op.create_table(
            "article_tags",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=191), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )

    if "articles" not in tables:
        op.create_table(
            "articles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=191), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.String(length=512), nullable=False),
            sa.Column("body", sa.Text(length=4294967295), nullable=False),
            sa.Column("body_format", sa.String(length=16), nullable=False),
            sa.Column("cover_url", sa.String(length=512), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("halo_source_id", sa.String(length=191), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
            sa.UniqueConstraint("halo_source_id", name="uq_articles_halo_source_id"),
        )
        op.create_index("ix_articles_status", "articles", ["status"])
        op.create_index("ix_articles_author_user_id", "articles", ["author_user_id"])
        op.create_index("ix_articles_published_at", "articles", ["published_at"])

    if "article_category_links" not in tables:
        op.create_table(
            "article_category_links",
            sa.Column("article_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["category_id"], ["article_categories.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("article_id", "category_id"),
        )

    if "article_tag_links" not in tables:
        op.create_table(
            "article_tag_links",
            sa.Column("article_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tag_id"], ["article_tags.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("article_id", "tag_id"),
        )

    if "article_comments" not in tables:
        op.create_table(
            "article_comments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("article_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("guest_name", sa.String(length=64), nullable=True),
            sa.Column("body", sa.String(length=2000), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["parent_id"], ["article_comments.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_article_comments_article_id", "article_comments", ["article_id"])
        op.create_index("ix_article_comments_user_id", "article_comments", ["user_id"])
        op.create_index("ix_article_comments_parent_id", "article_comments", ["parent_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "article_comments" in tables:
        op.drop_table("article_comments")
    if "article_tag_links" in tables:
        op.drop_table("article_tag_links")
    if "article_category_links" in tables:
        op.drop_table("article_category_links")
    if "articles" in tables:
        op.drop_table("articles")
    if "article_tags" in tables:
        op.drop_table("article_tags")
    if "article_categories" in tables:
        op.drop_table("article_categories")
