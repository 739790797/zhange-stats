"""Raid rooms: password on public desks; drop private rooms.

Revision ID: 20260831_0085
Revises: 20260831_0084
Create Date: 2026-08-31

MariaDB DDL is non-transactional; ADD COLUMN gated on inspect.
Deletes leftover unlisted (8-char) private rooms and their children.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0085"
down_revision: Union[str, Sequence[str], None] = "20260831_0084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SLOT_IDS = ("1", "2", "3", "4", "5", "pve-1", "pve-2", "pve-3", "pve-4", "pve-5")
_CHILD_TABLES = (
    "tarkov_raid_room_marks",
    "tarkov_raid_room_key_brings",
    "tarkov_raid_room_objective_dones",
    "tarkov_raid_room_task_claims",
    "tarkov_raid_room_members",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_raid_rooms" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_rooms")}
    if "password_hash" not in cols:
        op.add_column(
            "tarkov_raid_rooms",
            sa.Column("password_hash", sa.String(length=255), nullable=True),
        )
    quoted = ",".join(f"'{pid}'" for pid in _SLOT_IDS)
    ids = [
        int(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT id FROM tarkov_raid_rooms "
                f"WHERE public_id NOT IN ({quoted})"
            )
        )
    ]
    if ids:
        id_list = ",".join(str(i) for i in ids)
        for table in _CHILD_TABLES:
            if table in tables:
                bind.execute(
                    sa.text(f"DELETE FROM {table} WHERE room_id IN ({id_list})")
                )
        bind.execute(
            sa.text(f"DELETE FROM tarkov_raid_rooms WHERE id IN ({id_list})")
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_rooms" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_rooms")}
    if "password_hash" in cols:
        op.drop_column("tarkov_raid_rooms", "password_hash")
