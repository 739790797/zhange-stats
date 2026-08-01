"""Add steam_apps cache for localized game display names.

Revision ID: 20260801_0002
Revises: 20260731_0001
Create Date: 2026-08-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0002"
down_revision: Union[str, Sequence[str], None] = "20260731_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "steam_apps",
        sa.Column("app_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("app_id"),
    )


def downgrade() -> None:
    op.drop_table("steam_apps")
