"""Add tarkov raid room mark strokes (points_json).

Revision ID: 20260827_0070
Revises: 20260827_0069
Create Date: 2026-08-27

MariaDB note: JSON is LONGTEXT; do not CAST(... AS JSON).
MySQL/MariaDB DDL is non-transactional, so ADD COLUMN is gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260827_0070"
down_revision: Union[str, Sequence[str], None] = "20260827_0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_room_marks")}
    if "points_json" not in cols:
        op.add_column(
            "tarkov_raid_room_marks",
            sa.Column("points_json", mysql.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_room_marks")}
    if "points_json" in cols:
        op.drop_column("tarkov_raid_room_marks", "points_json")
