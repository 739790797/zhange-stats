"""Add tarkov map nav nodes and edges.

Revision ID: 20260906_0098
Revises: 20260906_0097
Create Date: 2026-09-06

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260906_0098"
down_revision: Union[str, Sequence[str], None] = "20260906_0097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
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


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
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
