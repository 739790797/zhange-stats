"""Raid room members last_seen_at for idle seat reclaim.

Revision ID: 20260829_0074
Revises: 20260829_0073
Create Date: 2026-08-29

MariaDB DDL is non-transactional; ADD COLUMN gated on inspect.
Existing rows get CURRENT_TIMESTAMP so deploy does not instantly kick seats.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0074"
down_revision: Union[str, Sequence[str], None] = "20260829_0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_members" not in tables:
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_room_members")}
    if "last_seen_at" in cols:
        return
    op.add_column(
        "tarkov_raid_room_members",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_members" not in tables:
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_room_members")}
    if "last_seen_at" in cols:
        op.drop_column("tarkov_raid_room_members", "last_seen_at")
