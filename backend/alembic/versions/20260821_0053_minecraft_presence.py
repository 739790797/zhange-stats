"""Minecraft player online/offline presence segments.

Revision ID: 20260821_0053
Revises: 20260821_0052
Create Date: 2026-08-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0053"
down_revision: Union[str, Sequence[str], None] = "20260821_0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "minecraft_presence_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player_key", sa.String(length=80), nullable=False),
        sa.Column("player_name", sa.String(length=64), nullable=False),
        sa.Column("player_uuid", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_minecraft_presence_segments_player_key",
        "minecraft_presence_segments",
        ["player_key"],
        unique=False,
    )
    op.create_index(
        "ix_minecraft_presence_segments_status",
        "minecraft_presence_segments",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_minecraft_presence_segments_started_at",
        "minecraft_presence_segments",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        "ix_minecraft_presence_segments_ended_at",
        "minecraft_presence_segments",
        ["ended_at"],
        unique=False,
    )
    op.create_index(
        "ix_mc_presence_player_started",
        "minecraft_presence_segments",
        ["player_key", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_mc_presence_player_ended",
        "minecraft_presence_segments",
        ["player_key", "ended_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mc_presence_player_ended", table_name="minecraft_presence_segments")
    op.drop_index(
        "ix_mc_presence_player_started", table_name="minecraft_presence_segments"
    )
    op.drop_index(
        "ix_minecraft_presence_segments_ended_at",
        table_name="minecraft_presence_segments",
    )
    op.drop_index(
        "ix_minecraft_presence_segments_started_at",
        table_name="minecraft_presence_segments",
    )
    op.drop_index(
        "ix_minecraft_presence_segments_status",
        table_name="minecraft_presence_segments",
    )
    op.drop_index(
        "ix_minecraft_presence_segments_player_key",
        table_name="minecraft_presence_segments",
    )
    op.drop_table("minecraft_presence_segments")
