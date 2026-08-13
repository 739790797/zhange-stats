"""Store Tarkov Tracker per-task progress snapshot.

Revision ID: 20260813_0048
Revises: 20260813_0047
Create Date: 2026-08-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0048"
down_revision: Union[str, Sequence[str], None] = "20260813_0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tarkov_tracker_binds",
        sa.Column("progress_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tarkov_tracker_binds", "progress_json")
