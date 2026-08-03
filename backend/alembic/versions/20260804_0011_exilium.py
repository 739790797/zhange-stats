"""Add exilium (追放社区) binds and checkin logs.

Revision ID: 20260804_0011
Revises: 20260803_0010
Create Date: 2026-08-04

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0011"
down_revision: Union[str, Sequence[str], None] = "20260803_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exilium_binds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("credentials_enc", sa.Text(), nullable=False),
        sa.Column("phone_mask", sa.String(length=64), nullable=True),
        sa.Column("auto_checkin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checkin_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checkin_date", sa.Date(), nullable=True),
        sa.Column("last_checkin_summary", sa.Text(), nullable=True),
        sa.Column("last_checkin_ok", sa.Boolean(), nullable=True),
        sa.Column(
            "bound_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id"),
    )
    op.create_table(
        "exilium_checkin_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("bind_id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=32), nullable=False),
        sa.Column("game_name", sa.String(length=64), nullable=False),
        sa.Column("role_uid", sa.String(length=64), nullable=False),
        sa.Column("role_name", sa.String(length=128), nullable=True),
        sa.Column("channel_name", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("awards_text", sa.String(length=512), nullable=True),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bind_id"], ["exilium_binds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id",
            "checkin_date",
            "game_code",
            "role_uid",
            name="uq_exilium_checkin_day_role",
        ),
    )
    op.create_index(
        "ix_exilium_checkin_logs_member_id",
        "exilium_checkin_logs",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        "ix_exilium_checkin_logs_bind_id",
        "exilium_checkin_logs",
        ["bind_id"],
        unique=False,
    )
    op.create_index(
        "ix_exilium_checkin_logs_checkin_date",
        "exilium_checkin_logs",
        ["checkin_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_exilium_checkin_logs_checkin_date", table_name="exilium_checkin_logs")
    op.drop_index("ix_exilium_checkin_logs_bind_id", table_name="exilium_checkin_logs")
    op.drop_index("ix_exilium_checkin_logs_member_id", table_name="exilium_checkin_logs")
    op.drop_table("exilium_checkin_logs")
    op.drop_table("exilium_binds")
