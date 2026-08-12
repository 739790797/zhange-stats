"""Drop Steam friend list cache (calendar is site-wide).

Revision ID: 20260812_0037
Revises: 20260812_0036
Create Date: 2026-08-12

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0037"
down_revision: Union[str, Sequence[str], None] = "20260812_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("steam_friend_edges")
    op.drop_column("members", "steam_friends_synced_at")
    op.drop_column("members", "steam_friends_public")


def downgrade() -> None:
    op.add_column(
        "members",
        sa.Column("steam_friends_public", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "members",
        sa.Column("steam_friends_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "steam_friend_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("friend_steam_id", sa.String(length=32), nullable=False),
        sa.Column("friend_since", sa.Integer(), nullable=True),
        sa.Column("nickname", sa.String(length=64), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "friend_steam_id", name="uq_steam_friend_edge"
        ),
    )
    op.create_index(
        op.f("ix_steam_friend_edges_friend_steam_id"),
        "steam_friend_edges",
        ["friend_steam_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_steam_friend_edges_member_id"),
        "steam_friend_edges",
        ["member_id"],
        unique=False,
    )
