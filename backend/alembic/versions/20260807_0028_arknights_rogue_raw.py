"""Add arknights_rogue_raws for integrated strategy (rogue) snapshots.

Revision ID: 20260807_0028
Revises: 20260806_0027
Create Date: 2026-08-07

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0028"
down_revision: Union[str, Sequence[str], None] = "20260806_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "arknights_rogue_raws",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=64), nullable=False),
        sa.Column("topic_id", sa.String(length=32), nullable=False),
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
            "member_id",
            "uid",
            "topic_id",
            name="uq_arknights_rogue_raw_member_uid_topic",
        ),
    )
    op.create_index(
        "ix_arknights_rogue_raws_member_id",
        "arknights_rogue_raws",
        ["member_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_arknights_rogue_raws_member_id", table_name="arknights_rogue_raws")
    op.drop_table("arknights_rogue_raws")
