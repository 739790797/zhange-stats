"""Add tarkov map place overlays.

Revision ID: 20260901_0088
Revises: 20260901_0087
Create Date: 2026-09-01

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260901_0088"
down_revision: Union[str, Sequence[str], None] = "20260901_0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_map_places" not in tables:
        op.create_table(
            "tarkov_map_places",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("map_key", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=8), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("x", sa.Float(), nullable=False),
            sa.Column("z", sa.Float(), nullable=False),
            sa.Column("x2", sa.Float(), nullable=True),
            sa.Column("z2", sa.Float(), nullable=True),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("floor", sa.String(length=64), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_tarkov_map_places_map_key",
            "tarkov_map_places",
            ["map_key", "sort_order"],
        )

    from app.core.timeutil import now_naive
    from app.services.tarkov.places import SHORELINE_SEED

    existing = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM tarkov_map_places WHERE map_key = :key"
        ),
        {"key": "shoreline"},
    ).scalar()
    if existing:
        return
    now = now_naive()
    rows = []
    for index, item in enumerate(SHORELINE_SEED, start=1):
        rows.append(
            {
                "map_key": "shoreline",
                "kind": "point",
                "name": item["name"],
                "x": item["x"],
                "z": item["z"],
                "x2": None,
                "z2": None,
                "size": int(item.get("size") or 80),
                "floor": "",
                "sort_order": index,
                "created_at": now,
                "updated_at": now,
            }
        )
    if rows:
        op.bulk_insert(sa.table(
            "tarkov_map_places",
            sa.column("map_key"),
            sa.column("kind"),
            sa.column("name"),
            sa.column("x"),
            sa.column("z"),
            sa.column("x2"),
            sa.column("z2"),
            sa.column("size"),
            sa.column("floor"),
            sa.column("sort_order"),
            sa.column("created_at"),
            sa.column("updated_at"),
        ), rows)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_map_places" in tables:
        op.drop_index("ix_tarkov_map_places_map_key", table_name="tarkov_map_places")
        op.drop_table("tarkov_map_places")
