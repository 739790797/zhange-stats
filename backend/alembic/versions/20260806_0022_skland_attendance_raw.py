"""Add skland_attendance_raws for arknights sign-in calendar cache.

Revision ID: 20260806_0022
Revises: 20260806_0021
Create Date: 2026-08-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0022"
down_revision: Union[str, Sequence[str], None] = "20260806_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skland_attendance_raws",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=64), nullable=False),
        sa.Column("channel_name", sa.String(length=64), nullable=True),
        sa.Column("role_name", sa.String(length=128), nullable=True),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "uid", name="uq_skland_attendance_raw_member_uid"
        ),
    )
    op.create_index(
        op.f("ix_skland_attendance_raws_member_id"),
        "skland_attendance_raws",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_skland_attendance_raws_member_id"),
        table_name="skland_attendance_raws",
    )
    op.drop_table("skland_attendance_raws")
