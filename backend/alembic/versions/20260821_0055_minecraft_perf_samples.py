"""Minecraft RCON TPS/MSPT time series samples.

Revision ID: 20260821_0055
Revises: 20260821_0054
Create Date: 2026-08-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0055"
down_revision: Union[str, Sequence[str], None] = "20260821_0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "minecraft_perf_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tps", sa.Float(), nullable=True),
        sa.Column("mspt", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_minecraft_perf_samples_sampled_at",
        "minecraft_perf_samples",
        ["sampled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_minecraft_perf_samples_sampled_at",
        table_name="minecraft_perf_samples",
    )
    op.drop_table("minecraft_perf_samples")
