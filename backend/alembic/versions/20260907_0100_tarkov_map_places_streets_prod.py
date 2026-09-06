"""Refresh streets places from the production overlay.

Revision ID: 20260907_0100
Revises: 20260907_0099
Create Date: 2026-09-07

MariaDB note: delete+insert gated on inspect. Skip if 小黄楼 already exists
so production (already on this snapshot) is not rewritten.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260907_0100"
down_revision: Union[str, Sequence[str], None] = "20260907_0099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MAP_KEY = "streets-of-tarkov"
MARKER_NAME = "小黄楼"

_PLACE_TABLE = sa.table(
    "tarkov_map_places",
    sa.column("map_key"),
    sa.column("kind"),
    sa.column("name"),
    sa.column("x"),
    sa.column("z"),
    sa.column("x2"),
    sa.column("z2"),
    sa.column("label_x"),
    sa.column("label_z"),
    sa.column("size"),
    sa.column("floor"),
    sa.column("sort_order"),
    sa.column("created_at"),
    sa.column("updated_at"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_map_places" not in tables:
        return
    marker = bind.execute(
        sa.text(
            "SELECT id FROM tarkov_map_places "
            "WHERE map_key = :key AND name = :name LIMIT 1"
        ),
        {"key": MAP_KEY, "name": MARKER_NAME},
    ).first()
    if marker is not None:
        return

    from app.core.timeutil import now_naive
    from app.services.tarkov.places import STREETS_OF_TARKOV_SEED, place_seed_rows

    bind.execute(
        sa.text("DELETE FROM tarkov_map_places WHERE map_key = :key"),
        {"key": MAP_KEY},
    )
    rows = place_seed_rows(MAP_KEY, STREETS_OF_TARKOV_SEED, now_naive())
    if rows:
        op.bulk_insert(_PLACE_TABLE, rows)


def downgrade() -> None:
    return
