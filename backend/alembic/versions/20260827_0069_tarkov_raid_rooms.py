"""Add tarkov raid prep rooms, members, task claims, and board marks.

Revision ID: 20260827_0069
Revises: 20260827_0068
Create Date: 2026-08-27

MySQL/MariaDB DDL is non-transactional; CREATE TABLE is gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0069"
down_revision: Union[str, Sequence[str], None] = "20260827_0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "tarkov_raid_rooms" not in tables:
        op.create_table(
            "tarkov_raid_rooms",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=16), nullable=False),
            sa.Column("title", sa.String(length=40), nullable=False),
            sa.Column("map_slug", sa.String(length=64), nullable=False),
            sa.Column("host_user_id", sa.Integer(), nullable=False),
            sa.Column("host_display_name", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["host_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_id"),
        )
        op.create_index(
            "ix_tarkov_raid_rooms_host_user_id",
            "tarkov_raid_rooms",
            ["host_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_tarkov_raid_rooms_status",
            "tarkov_raid_rooms",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_tarkov_raid_rooms_status_created",
            "tarkov_raid_rooms",
            ["status", "created_at"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_members" not in tables:
        op.create_table(
            "tarkov_raid_room_members",
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("display_name", sa.String(length=64), nullable=False),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["room_id"], ["tarkov_raid_rooms.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("room_id", "user_id"),
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_task_claims" not in tables:
        op.create_table(
            "tarkov_raid_room_task_claims",
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["room_id"], ["tarkov_raid_rooms.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("room_id", "task_id", "user_id"),
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        op.create_table(
            "tarkov_raid_room_marks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=8), nullable=False),
            sa.Column("floor", sa.String(length=64), nullable=False),
            sa.Column("x", sa.Float(), nullable=False),
            sa.Column("z", sa.Float(), nullable=False),
            sa.Column("x2", sa.Float(), nullable=True),
            sa.Column("z2", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["room_id"], ["tarkov_raid_rooms.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["author_user_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_tarkov_raid_room_marks_room",
            "tarkov_raid_room_marks",
            ["room_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" in tables:
        op.drop_index(
            "ix_tarkov_raid_room_marks_room", table_name="tarkov_raid_room_marks"
        )
        op.drop_table("tarkov_raid_room_marks")
    if "tarkov_raid_room_task_claims" in tables:
        op.drop_table("tarkov_raid_room_task_claims")
    if "tarkov_raid_room_members" in tables:
        op.drop_table("tarkov_raid_room_members")
    if "tarkov_raid_rooms" in tables:
        op.drop_index(
            "ix_tarkov_raid_rooms_status_created", table_name="tarkov_raid_rooms"
        )
        op.drop_index("ix_tarkov_raid_rooms_status", table_name="tarkov_raid_rooms")
        op.drop_index(
            "ix_tarkov_raid_rooms_host_user_id", table_name="tarkov_raid_rooms"
        )
        op.drop_table("tarkov_raid_rooms")
