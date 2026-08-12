"""Add tarkov_ammo.icon_link.

Revision ID: 20260812_0042
Revises: 20260812_0041
Create Date: 2026-08-12

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0042"
down_revision: Union[str, Sequence[str], None] = "20260812_0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tarkov_ammo",
        sa.Column("icon_link", sa.String(length=512), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("tarkov_ammo", "icon_link")
