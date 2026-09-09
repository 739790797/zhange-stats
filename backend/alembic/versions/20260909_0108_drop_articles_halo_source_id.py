"""Drop articles.halo_source_id (Halo import removed).

Revision ID: 20260909_0108
Revises: 20260909_0107
Create Date: 2026-09-09

MariaDB note: unique may appear as constraint or index; both gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0108"
down_revision: Union[str, Sequence[str], None] = "20260909_0107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UQ = "uq_articles_halo_source_id"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "articles" not in set(inspector.get_table_names()):
        return
    uniques = {uc["name"] for uc in inspector.get_unique_constraints("articles")}
    indexes = {ix["name"] for ix in inspector.get_indexes("articles")}
    if _UQ in uniques:
        op.drop_constraint(_UQ, "articles", type_="unique")
    elif _UQ in indexes:
        op.drop_index(_UQ, table_name="articles")
    cols = {c["name"] for c in inspector.get_columns("articles")}
    if "halo_source_id" in cols:
        op.drop_column("articles", "halo_source_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "articles" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("articles")}
    if "halo_source_id" not in cols:
        op.add_column(
            "articles",
            sa.Column("halo_source_id", sa.String(length=191), nullable=True),
        )
    uniques = {uc["name"] for uc in inspector.get_unique_constraints("articles")}
    indexes = {ix["name"] for ix in inspector.get_indexes("articles")}
    if _UQ not in uniques and _UQ not in indexes:
        op.create_unique_constraint(_UQ, "articles", ["halo_source_id"])
