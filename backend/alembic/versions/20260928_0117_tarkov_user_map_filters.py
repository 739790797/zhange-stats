"""Add per-user Tarkov map filter preferences.

Revision ID: 20260928_0117
Revises: 20260928_0116
Create Date: 2026-09-28

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
JSON columns cannot use DEFAULT; the app writes the prefs object.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0117"
down_revision: Union[str, Sequence[str], None] = "20260928_0116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_map_filters" in tables:
        return
    op.create_table(
        "tarkov_user_map_filters",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("prefs", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_map_filters" in tables:
        op.drop_table("tarkov_user_map_filters")
