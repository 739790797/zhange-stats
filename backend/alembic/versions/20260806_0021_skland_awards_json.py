"""Add awards_json to skland_checkin_logs for structured reward icons.

Revision ID: 20260806_0021
Revises: 20260805_0020
Create Date: 2026-08-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0021"
down_revision: Union[str, Sequence[str], None] = "20260805_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skland_checkin_logs",
        sa.Column("awards_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skland_checkin_logs", "awards_json")
