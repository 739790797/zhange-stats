"""Add rum_samples for browser wait-time stats.

Revision ID: 20260911_0110
Revises: 20260911_0109
Create Date: 2026-09-11

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0110"
down_revision: Union[str, Sequence[str], None] = "20260911_0109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "rum_samples" in tables:
        return
    op.create_table(
        "rum_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("url_key", sa.String(length=256), nullable=False),
        sa.Column("host", sa.String(length=128), nullable=False),
        sa.Column("page_path", sa.String(length=256), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("transfer_size", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rum_samples_recorded_at", "rum_samples", ["recorded_at"])
    op.create_index(
        "ix_rum_samples_kind_recorded", "rum_samples", ["kind", "recorded_at"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "rum_samples" not in tables:
        return
    op.drop_index("ix_rum_samples_kind_recorded", table_name="rum_samples")
    op.drop_index("ix_rum_samples_recorded_at", table_name="rum_samples")
    op.drop_table("rum_samples")
