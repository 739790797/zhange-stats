"""Seed remaining map places from the last upstream snapshot.

Revision ID: 20260907_0099
Revises: 20260906_0098
Create Date: 2026-09-07

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
Insert skips a map_key that already has rows (shoreline / streets).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260907_0099"
down_revision: Union[str, Sequence[str], None] = "20260906_0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
    sa.column("top"),
    sa.column("bottom"),
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
    cols = {c["name"] for c in inspector.get_columns("tarkov_map_places")}
    if "top" not in cols:
        op.add_column("tarkov_map_places", sa.Column("top", sa.Float(), nullable=True))
    if "bottom" not in cols:
        op.add_column(
            "tarkov_map_places",
            sa.Column("bottom", sa.Float(), nullable=True),
        )

    from app.core.timeutil import now_naive
    from app.services.tarkov.places import UPSTREAM_PLACE_SEED, place_seed_rows

    now = now_naive()
    for map_key, items in UPSTREAM_PLACE_SEED.items():
        if not items:
            continue
        existing = bind.execute(
            sa.text("SELECT COUNT(*) FROM tarkov_map_places WHERE map_key = :key"),
            {"key": map_key},
        ).scalar()
        if existing:
            continue
        rows = place_seed_rows(map_key, items, now)
        if rows:
            op.bulk_insert(_PLACE_TABLE, rows)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_map_places" not in tables:
        return

    from app.services.tarkov.places import UPSTREAM_PLACE_SEED

    for map_key in UPSTREAM_PLACE_SEED:
        bind.execute(
            sa.text("DELETE FROM tarkov_map_places WHERE map_key = :key"),
            {"key": map_key},
        )
    cols = {c["name"] for c in inspector.get_columns("tarkov_map_places")}
    if "bottom" in cols:
        op.drop_column("tarkov_map_places", "bottom")
    if "top" in cols:
        op.drop_column("tarkov_map_places", "top")
