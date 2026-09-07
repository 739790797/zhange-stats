"""Tavern authors and article versions.

Revision ID: 20260907_0103
Revises: 20260907_0102
Create Date: 2026-09-07

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0103"
down_revision: Union[str, Sequence[str], None] = "20260907_0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "article_authors" not in tables:
        op.create_table(
            "article_authors",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if "article_versions" not in tables:
        op.create_table(
            "article_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("article_id", sa.Integer(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.String(length=512), nullable=False),
            sa.Column("body", sa.Text(length=4294967295), nullable=False),
            sa.Column("body_format", sa.String(length=16), nullable=False),
            sa.Column("cover_url", sa.String(length=512), nullable=True),
            sa.Column("note", sa.String(length=128), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("article_id", "version_no", name="uq_article_versions_no"),
        )
        op.create_index("ix_article_versions_article_id", "article_versions", ["article_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "article_versions" in tables:
        op.drop_table("article_versions")
    if "article_authors" in tables:
        op.drop_table("article_authors")
