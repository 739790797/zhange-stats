"""Raid room members: in-progress task ids for map overlap.

Revision ID: 20260831_0083
Revises: 20260831_0082
Create Date: 2026-08-31

MariaDB DDL is non-transactional; ADD COLUMN gated on inspect.
TEXT/JSON cannot use DEFAULT on this MariaDB; backfill then MODIFY NOT NULL.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0083"
down_revision: Union[str, Sequence[str], None] = "20260831_0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_members" not in tables:
        return
    cols = {c["name"]: c for c in sa.inspect(bind).get_columns("tarkov_raid_room_members")}
    if "started_task_ids_json" not in cols:
        op.add_column(
            "tarkov_raid_room_members",
            sa.Column("started_task_ids_json", sa.Text(), nullable=True),
        )
        cols = {
            c["name"]: c
            for c in sa.inspect(bind).get_columns("tarkov_raid_room_members")
        }
    started = cols.get("started_task_ids_json")
    if started is not None and started.get("nullable", True):
        op.execute(
            sa.text(
                "UPDATE tarkov_raid_room_members "
                "SET started_task_ids_json = '[]' "
                "WHERE started_task_ids_json IS NULL"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE tarkov_raid_room_members "
                "MODIFY COLUMN started_task_ids_json TEXT NOT NULL"
            )
        )
    if "task_progress_at" not in cols:
        op.add_column(
            "tarkov_raid_room_members",
            sa.Column("task_progress_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_members" not in tables:
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_room_members")}
    if "task_progress_at" in cols:
        op.drop_column("tarkov_raid_room_members", "task_progress_at")
    if "started_task_ids_json" in cols:
        op.drop_column("tarkov_raid_room_members", "started_task_ids_json")
