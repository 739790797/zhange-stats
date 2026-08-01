"""Add steam_persona_name to members for follow-on-rename tracking.

Revision ID: 20260801_0005
Revises: 20260801_0004
Create Date: 2026-08-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0005"
down_revision: Union[str, Sequence[str], None] = "20260801_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("steam_persona_name", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("members", "steam_persona_name")
