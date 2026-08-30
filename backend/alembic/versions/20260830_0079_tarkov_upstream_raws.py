"""Add tarkov upstream full-site raw dump.

Revision ID: 20260830_0079
Revises: 20260830_0078
Create Date: 2026-08-30

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0079"
down_revision: Union[str, Sequence[str], None] = "20260830_0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_upstream_raws" in tables:
        return
    op.create_table(
        "tarkov_upstream_raws",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mode_id", sa.Integer(), nullable=False),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "mode_id",
            "resource",
            name="uq_tarkov_upstream_raws_mode_resource",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_upstream_raws" not in tables:
        return
    op.drop_table("tarkov_upstream_raws")
