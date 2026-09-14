"""Add tarkov user profiles.

Revision ID: 20260914_0113
Revises: 20260914_0112
Create Date: 2026-09-14

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
JSON columns cannot use DEFAULT; app writes {}.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0113"
down_revision: Union[str, Sequence[str], None] = "20260914_0112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_profiles" in tables:
        return
    op.create_table(
        "tarkov_user_profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_mode", sa.String(length=8), nullable=False),
        sa.Column("pmc_faction", sa.String(length=8), nullable=False),
        sa.Column("game_edition", sa.String(length=16), nullable=False),
        sa.Column("player_level", sa.Integer(), nullable=False),
        sa.Column("trader_levels", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "game_mode"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_profiles" in tables:
        op.drop_table("tarkov_user_profiles")
