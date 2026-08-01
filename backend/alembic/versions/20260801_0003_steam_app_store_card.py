"""Add Steam store card fields to steam_apps.

Revision ID: 20260801_0003
Revises: 20260801_0002
Create Date: 2026-08-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0003"
down_revision: Union[str, Sequence[str], None] = "20260801_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "steam_apps", sa.Column("header_image", sa.String(length=512), nullable=True)
    )
    op.add_column("steam_apps", sa.Column("short_description", sa.Text(), nullable=True))
    op.add_column(
        "steam_apps",
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "steam_apps", sa.Column("currency", sa.String(length=8), nullable=True)
    )
    op.add_column("steam_apps", sa.Column("initial_price", sa.Integer(), nullable=True))
    op.add_column("steam_apps", sa.Column("final_price", sa.Integer(), nullable=True))
    op.add_column(
        "steam_apps", sa.Column("discount_percent", sa.Integer(), nullable=True)
    )
    op.add_column(
        "steam_apps",
        sa.Column("initial_formatted", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "steam_apps", sa.Column("final_formatted", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "steam_apps",
        sa.Column("details_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("steam_apps", "details_fetched_at")
    op.drop_column("steam_apps", "final_formatted")
    op.drop_column("steam_apps", "initial_formatted")
    op.drop_column("steam_apps", "discount_percent")
    op.drop_column("steam_apps", "final_price")
    op.drop_column("steam_apps", "initial_price")
    op.drop_column("steam_apps", "currency")
    op.drop_column("steam_apps", "is_free")
    op.drop_column("steam_apps", "short_description")
    op.drop_column("steam_apps", "header_image")
