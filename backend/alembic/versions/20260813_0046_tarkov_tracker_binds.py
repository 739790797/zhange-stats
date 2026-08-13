"""Add tarkov tracker bind table.

Revision ID: 20260813_0046
Revises: 20260813_0045
Create Date: 2026-08-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0046"
down_revision: Union[str, Sequence[str], None] = "20260813_0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tarkov_tracker_binds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("token_suffix", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("game_mode", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("display_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("player_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pmc_faction", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("game_edition", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_complete", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tasks_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "bound_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("tarkov_tracker_binds")
