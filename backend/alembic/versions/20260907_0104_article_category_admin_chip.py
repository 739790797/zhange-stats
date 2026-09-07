"""Article category admin-only flag and chip color.

Revision ID: 20260907_0104
Revises: 20260907_0103
Create Date: 2026-09-07

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0104"
down_revision: Union[str, Sequence[str], None] = "20260907_0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "article_categories" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("article_categories")}
    if "admin_only" not in cols:
        op.add_column(
            "article_categories",
            sa.Column(
                "admin_only",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    if "chip_color" not in cols:
        op.add_column(
            "article_categories",
            sa.Column("chip_color", sa.String(length=16), nullable=True),
        )

    from app.services.articles.defaults import DEFAULT_CATEGORIES

    for spec in DEFAULT_CATEGORIES:
        bind.execute(
            sa.text(
                "UPDATE article_categories SET admin_only = :admin_only, "
                "chip_color = CASE WHEN chip_color IS NULL OR chip_color = '' "
                "THEN :chip_color ELSE chip_color END WHERE slug = :slug"
            ),
            {
                "admin_only": 1 if spec.admin_only else 0,
                "chip_color": spec.chip_color,
                "slug": spec.slug,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "article_categories" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("article_categories")}
    if "chip_color" in cols:
        op.drop_column("article_categories", "chip_color")
    if "admin_only" in cols:
        op.drop_column("article_categories", "admin_only")
