"""Seed streets-of-tarkov map places from the development overlay.

Revision ID: 20260901_0090
Revises: 20260901_0089
Create Date: 2026-09-01

MariaDB note: DDL is non-transactional; insert gated on inspect + empty map.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260901_0090"
down_revision: Union[str, Sequence[str], None] = "20260901_0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MAP_KEY = "streets-of-tarkov"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_map_places" not in tables:
        return

    from app.core.timeutil import now_naive
    from app.services.tarkov.places import STREETS_OF_TARKOV_SEED, place_seed_rows

    existing = bind.execute(
        sa.text("SELECT COUNT(*) FROM tarkov_map_places WHERE map_key = :key"),
        {"key": MAP_KEY},
    ).scalar()
    if existing:
        return
    rows = place_seed_rows(MAP_KEY, STREETS_OF_TARKOV_SEED, now_naive())
    if not rows:
        return
    op.bulk_insert(
        sa.table(
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
        ),
        rows,
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_map_places" not in tables:
        return
    bind.execute(
        sa.text("DELETE FROM tarkov_map_places WHERE map_key = :key"),
        {"key": MAP_KEY},
    )
