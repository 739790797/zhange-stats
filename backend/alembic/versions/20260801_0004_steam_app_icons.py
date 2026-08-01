"""Add capsule_image and icon_url to steam_apps.

Revision ID: 20260801_0004
Revises: 20260801_0003
Create Date: 2026-08-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0004"
down_revision: Union[str, Sequence[str], None] = "20260801_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "steam_apps", sa.Column("capsule_image", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "steam_apps", sa.Column("icon_url", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("steam_apps", "icon_url")
    op.drop_column("steam_apps", "capsule_image")
