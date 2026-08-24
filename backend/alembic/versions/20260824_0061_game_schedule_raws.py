"""Add game_schedule_raws for activity calendar cache.

Revision ID: 20260824_0061
Revises: 20260824_0060
Create Date: 2026-08-24

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0061"
down_revision: Union[str, Sequence[str], None] = "20260824_0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_schedule_raws",
        sa.Column("game", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("upstream_base", sa.String(length=256), nullable=True),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("game"),
    )


def downgrade() -> None:
    op.drop_table("game_schedule_raws")
