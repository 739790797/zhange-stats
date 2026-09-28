"""Mark raid-room strokes with a map and clear the room map.

Revision ID: 20260928_0115
Revises: 20260914_0114
Create Date: 2026-09-28

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260928_0115"
down_revision: Union[str, Sequence[str], None] = "20260914_0114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns("tarkov_raid_room_marks")}
    if "map_slug" not in cols:
        op.add_column(
            "tarkov_raid_room_marks",
            sa.Column("map_slug", sa.String(length=64), nullable=False, server_default=""),
        )
    if "tarkov_raid_rooms" not in tables:
        return
    rooms = bind.execute(
        sa.text("SELECT id, map_slug FROM tarkov_raid_rooms")
    ).fetchall()
    for room_id, map_slug in rooms:
        slug = str(map_slug or "").strip()
        if not slug:
            continue
        bind.execute(
            sa.text(
                "UPDATE tarkov_raid_room_marks SET map_slug = :slug "
                "WHERE room_id = :room_id AND (map_slug = '' OR map_slug IS NULL)"
            ),
            {"slug": slug, "room_id": room_id},
        )
    bind.execute(sa.text("UPDATE tarkov_raid_rooms SET map_slug = ''"))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns("tarkov_raid_room_marks")}
    if "map_slug" in cols:
        op.drop_column("tarkov_raid_room_marks", "map_slug")
