"""Minecraft perf samples: entities + chunks columns.

Revision ID: 20260822_0059
Revises: 20260821_0058
Create Date: 2026-08-22

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0059"
down_revision: Union[str, Sequence[str], None] = "20260821_0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "minecraft_perf_samples",
        sa.Column("entities", sa.Float(), nullable=True),
    )
    op.add_column(
        "minecraft_perf_samples",
        sa.Column("chunks", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("minecraft_perf_samples", "chunks")
    op.drop_column("minecraft_perf_samples", "entities")
