"""Add nickname (friend alias) to steam_friend_edges.

Revision ID: 20260801_0006
Revises: 20260801_0005
Create Date: 2026-08-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0006"
down_revision: Union[str, Sequence[str], None] = "20260801_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "steam_friend_edges",
        sa.Column("nickname", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("steam_friend_edges", "nickname")
