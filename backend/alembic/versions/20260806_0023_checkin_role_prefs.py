"""Add checkin_role_prefs for per-role auto checkin schedule.

Revision ID: 20260806_0023
Revises: 20260806_0022
Create Date: 2026-08-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0023"
down_revision: Union[str, Sequence[str], None] = "20260806_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checkin_role_prefs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=32), nullable=False),
        sa.Column("role_uid", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("checkin_hour", sa.Integer(), nullable=True),
        sa.Column("checkin_minute", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform",
            "member_id",
            "game_code",
            "role_uid",
            name="uq_checkin_role_pref",
        ),
    )
    op.create_index(
        "ix_checkin_role_prefs_platform", "checkin_role_prefs", ["platform"], unique=False
    )
    op.create_index(
        "ix_checkin_role_prefs_member_id",
        "checkin_role_prefs",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_checkin_role_prefs_member_id", table_name="checkin_role_prefs")
    op.drop_index("ix_checkin_role_prefs_platform", table_name="checkin_role_prefs")
    op.drop_table("checkin_role_prefs")
