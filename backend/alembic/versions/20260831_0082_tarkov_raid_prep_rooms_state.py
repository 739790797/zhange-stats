"""Raid rooms: game mode, private rooms, exclusive claims; solo raid prep.

Revision ID: 20260831_0082
Revises: 20260830_0081
Create Date: 2026-08-31

MariaDB note: DDL is non-transactional; ADD COLUMN / CREATE TABLE gated on inspect.
JSON columns cannot use DEFAULT; app writes [].
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260831_0082"
down_revision: Union[str, Sequence[str], None] = "20260830_0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "tarkov_raid_rooms" in tables:
        cols = {c["name"] for c in inspector.get_columns("tarkov_raid_rooms")}
        if "game_mode" not in cols:
            op.add_column(
                "tarkov_raid_rooms",
                sa.Column(
                    "game_mode",
                    sa.String(length=8),
                    nullable=False,
                    server_default="pvp",
                ),
            )
        if "listed" not in cols:
            op.add_column(
                "tarkov_raid_rooms",
                sa.Column(
                    "listed",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                ),
            )

    if "tarkov_raid_room_task_claims" in tables:
        cols = {c["name"] for c in inspector.get_columns("tarkov_raid_room_task_claims")}
        if "exclusive" not in cols:
            op.add_column(
                "tarkov_raid_room_task_claims",
                sa.Column(
                    "exclusive",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )

    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_raid_preps" not in tables:
        op.create_table(
            "tarkov_user_raid_preps",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("game_mode", sa.String(length=8), nullable=False),
            sa.Column("map_slug", sa.String(length=64), nullable=False),
            sa.Column("selected_json", mysql.JSON(), nullable=False),
            sa.Column("objective_dones_json", mysql.JSON(), nullable=False),
            sa.Column("key_brings_json", mysql.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "game_mode", "map_slug"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_user_raid_preps" in tables:
        op.drop_table("tarkov_user_raid_preps")
    if "tarkov_raid_room_task_claims" in tables:
        cols = {c["name"] for c in inspector.get_columns("tarkov_raid_room_task_claims")}
        if "exclusive" in cols:
            op.drop_column("tarkov_raid_room_task_claims", "exclusive")
    if "tarkov_raid_rooms" in tables:
        cols = {c["name"] for c in inspector.get_columns("tarkov_raid_rooms")}
        if "listed" in cols:
            op.drop_column("tarkov_raid_rooms", "listed")
        if "game_mode" in cols:
            op.drop_column("tarkov_raid_rooms", "game_mode")
