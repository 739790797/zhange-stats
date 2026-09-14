"""Drop tarkov_raid_room_members.left_at (leave deletes the row).

Revision ID: 20260914_0112
Revises: 20260911_0111
Create Date: 2026-09-14

MariaDB note: DDL is non-transactional; DELETE/DROP gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0112"
down_revision: Union[str, Sequence[str], None] = "20260911_0111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_room_members" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_room_members")}
    if "left_at" not in cols:
        return
    op.execute(
        sa.text("DELETE FROM tarkov_raid_room_members WHERE left_at IS NOT NULL")
    )
    op.drop_column("tarkov_raid_room_members", "left_at")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_room_members" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_room_members")}
    if "left_at" in cols:
        return
    op.add_column(
        "tarkov_raid_room_members",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
