"""Seed PVE public raid-prep seats (pve-1 … pve-5).

Revision ID: 20260831_0084
Revises: 20260831_0083
Create Date: 2026-08-31

Public desks are mode-locked: 1–5 stay PVP; pve-1–pve-5 are PVE.
MariaDB DDL is non-transactional; INSERT gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0084"
down_revision: Union[str, Sequence[str], None] = "20260831_0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_rooms" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_rooms")}
    if "game_mode" not in cols or "listed" not in cols:
        return
    existing = {
        str(row[0])
        for row in bind.execute(sa.text("SELECT public_id FROM tarkov_raid_rooms"))
    }
    bind.execute(
        sa.text(
            "UPDATE tarkov_raid_rooms SET game_mode = 'pvp' "
            "WHERE public_id IN ('1','2','3','4','5')"
        )
    )
    for n in range(1, 6):
        pid = f"pve-{n}"
        if pid in existing:
            bind.execute(
                sa.text(
                    "UPDATE tarkov_raid_rooms SET game_mode = 'pve', listed = 1, "
                    "title = :title WHERE public_id = :pid"
                ),
                {"title": f"{n}号房", "pid": pid},
            )
            continue
        bind.execute(
            sa.text(
                "INSERT INTO tarkov_raid_rooms "
                "(public_id, title, map_slug, game_mode, listed, "
                "host_user_id, host_display_name, created_at) "
                "VALUES (:pid, :title, '', 'pve', 1, NULL, '', CURRENT_TIMESTAMP)"
            ),
            {"pid": pid, "title": f"{n}号房"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_rooms" not in inspector.get_table_names():
        return
    bind.execute(
        sa.text(
            "DELETE FROM tarkov_raid_rooms "
            "WHERE public_id IN ('pve-1','pve-2','pve-3','pve-4','pve-5') "
            "AND host_user_id IS NULL"
        )
    )
