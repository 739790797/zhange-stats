"""Add included flag to checkin_role_prefs for site membership.

Revision ID: 20260807_0029
Revises: 20260807_0028
Create Date: 2026-08-07

存量行默认 included=true（行为与改造前接近）；应用层对新种子角色写 included=false。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0029"
down_revision: Union[str, Sequence[str], None] = "20260807_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "checkin_role_prefs",
        sa.Column(
            "included",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )


def downgrade() -> None:
    op.drop_column("checkin_role_prefs", "included")
