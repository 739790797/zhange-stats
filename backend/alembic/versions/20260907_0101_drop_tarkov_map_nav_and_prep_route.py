"""Drop unused map nav tables and raid-prep route JSON.

Revision ID: 20260907_0101
Revises: 20260907_0100
Create Date: 2026-09-07

MariaDB note: DDL is non-transactional; DROP gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0101"
down_revision: Union[str, Sequence[str], None] = "20260907_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_map_nav_edges" in tables:
        op.drop_index(
            "ix_tarkov_map_nav_edges_map_key",
            table_name="tarkov_map_nav_edges",
        )
        op.drop_table("tarkov_map_nav_edges")
    if "tarkov_map_nav_nodes" in tables:
        op.drop_index(
            "ix_tarkov_map_nav_nodes_map_key",
            table_name="tarkov_map_nav_nodes",
        )
        op.drop_table("tarkov_map_nav_nodes")
    if "tarkov_user_raid_preps" in tables:
        cols = {c["name"] for c in inspector.get_columns("tarkov_user_raid_preps")}
        if "route_json" in cols:
            op.drop_column("tarkov_user_raid_preps", "route_json")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_user_raid_preps" in tables:
        cols = {c["name"] for c in inspector.get_columns("tarkov_user_raid_preps")}
        if "route_json" not in cols:
            op.add_column(
                "tarkov_user_raid_preps",
                sa.Column("route_json", sa.JSON(), nullable=True),
            )
    if "tarkov_map_nav_nodes" not in tables:
        op.create_table(
            "tarkov_map_nav_nodes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("map_key", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("x", sa.Float(), nullable=False),
            sa.Column("z", sa.Float(), nullable=False),
            sa.Column("floor", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_tarkov_map_nav_nodes_map_key",
            "tarkov_map_nav_nodes",
            ["map_key"],
        )
    if "tarkov_map_nav_edges" not in tables:
        op.create_table(
            "tarkov_map_nav_edges",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("map_key", sa.String(length=64), nullable=False),
            sa.Column("from_id", sa.Integer(), nullable=False),
            sa.Column("to_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["from_id"],
                ["tarkov_map_nav_nodes.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["to_id"],
                ["tarkov_map_nav_nodes.id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "map_key",
                "from_id",
                "to_id",
                name="uq_tarkov_map_nav_edges_pair",
            ),
        )
        op.create_index(
            "ix_tarkov_map_nav_edges_map_key",
            "tarkov_map_nav_edges",
            ["map_key"],
        )
