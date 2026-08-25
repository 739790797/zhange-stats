"""Add mihoyo_attendance_raws for game sign-in calendar cache.

Revision ID: 20260825_0063
Revises: 20260824_0062
Create Date: 2026-08-25

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0063"
down_revision: Union[str, Sequence[str], None] = "20260824_0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mihoyo_attendance_raws",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=32), nullable=False),
        sa.Column("role_uid", sa.String(length=64), nullable=False),
        sa.Column("role_name", sa.String(length=128), nullable=True),
        sa.Column("game_name", sa.String(length=64), nullable=True),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["member_id"], ["members.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id",
            "game_code",
            "role_uid",
            name="uq_mihoyo_attendance_raw_member_game_role",
        ),
    )
    op.create_index(
        op.f("ix_mihoyo_attendance_raws_member_id"),
        "mihoyo_attendance_raws",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_mihoyo_attendance_raws_member_id"),
        table_name="mihoyo_attendance_raws",
    )
    op.drop_table("mihoyo_attendance_raws")
