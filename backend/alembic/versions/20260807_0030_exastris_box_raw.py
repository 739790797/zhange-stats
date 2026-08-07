"""Add exastris_box_raws for 异环 characters snapshots.

Revision ID: 20260807_0030
Revises: 20260807_0029
Create Date: 2026-08-07

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0030"
down_revision: Union[str, Sequence[str], None] = "20260807_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exastris_box_raws",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.Column("uid", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "role_id", name="uq_exastris_box_raw_member_role"),
    )
    op.create_index(
        op.f("ix_exastris_box_raws_member_id"),
        "exastris_box_raws",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_exastris_box_raws_member_id"), table_name="exastris_box_raws")
    op.drop_table("exastris_box_raws")
