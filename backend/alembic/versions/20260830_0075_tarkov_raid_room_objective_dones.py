"""Add tarkov raid room per-user objective-done marks.

Revision ID: 20260830_0075
Revises: 20260829_0074
Create Date: 2026-08-30

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0075"
down_revision: Union[str, Sequence[str], None] = "20260829_0074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_objective_dones" in tables:
        return
    if "tarkov_raid_rooms" not in tables:
        return
    op.create_table(
        "tarkov_raid_room_objective_dones",
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("objective_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["room_id"], ["tarkov_raid_rooms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("room_id", "task_id", "objective_id", "user_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_objective_dones" in tables:
        op.drop_table("tarkov_raid_room_objective_dones")
