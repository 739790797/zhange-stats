"""Add tarkov raid room indexes for archive and lobby map filter.

Revision ID: 20260828_0071
Revises: 20260827_0070
Create Date: 2026-08-28

MariaDB note: DDL is non-transactional; create_index gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0071"
down_revision: Union[str, Sequence[str], None] = "20260827_0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_rooms" not in tables:
        return
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("tarkov_raid_rooms")}
    if "ix_tarkov_raid_rooms_status_expire" not in indexes:
        op.create_index(
            "ix_tarkov_raid_rooms_status_expire",
            "tarkov_raid_rooms",
            ["status", "expire_at"],
        )
    if "ix_tarkov_raid_rooms_map_slug" not in indexes:
        op.create_index(
            "ix_tarkov_raid_rooms_map_slug",
            "tarkov_raid_rooms",
            ["map_slug"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_rooms" not in tables:
        return
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("tarkov_raid_rooms")}
    if "ix_tarkov_raid_rooms_map_slug" in indexes:
        op.drop_index("ix_tarkov_raid_rooms_map_slug", table_name="tarkov_raid_rooms")
    if "ix_tarkov_raid_rooms_status_expire" in indexes:
        op.drop_index(
            "ix_tarkov_raid_rooms_status_expire", table_name="tarkov_raid_rooms"
        )
