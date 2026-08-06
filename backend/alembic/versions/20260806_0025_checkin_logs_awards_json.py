"""Add awards_json to taygedo/exilium/kujiequ checkin logs.

Revision ID: 20260806_0025
Revises: 20260806_0024
Create Date: 2026-08-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0025"
down_revision: Union[str, Sequence[str], None] = "20260806_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "taygedo_checkin_logs",
        sa.Column("awards_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "exilium_checkin_logs",
        sa.Column("awards_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "kujiequ_checkin_logs",
        sa.Column("awards_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kujiequ_checkin_logs", "awards_json")
    op.drop_column("exilium_checkin_logs", "awards_json")
    op.drop_column("taygedo_checkin_logs", "awards_json")
