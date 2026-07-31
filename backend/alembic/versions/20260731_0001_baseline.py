"""Baseline schema matching current SQLAlchemy models.

Revision ID: 20260731_0001
Revises:
Create Date: 2026-07-31

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260731_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OBSOLETE_TABLES = (
    "cs2_match_players",
    "cs2_matches",
    "match_records",
    "games",
)


def upgrade() -> None:
    for name in _OBSOLETE_TABLES:
        op.execute(sa.text(f"DROP TABLE IF EXISTS `{name}`"))

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="userrole"),
            nullable=False,
        ),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_key", sa.String(length=64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("stats", mysql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_runs_job_key"), "job_runs", ["job_key"], unique=False)

    op.create_table(
        "register_challenges",
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )

    op.create_table(
        "system_configs",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("steam_id", sa.String(length=32), nullable=True),
        sa.Column("steam_friends_public", sa.Boolean(), nullable=True),
        sa.Column("steam_friends_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_members_nickname"), "members", ["nickname"], unique=False)
    op.create_index(op.f("ix_members_steam_id"), "members", ["steam_id"], unique=True)

    op.create_table(
        "play_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("steam_app_id", sa.String(length=32), nullable=False),
        sa.Column("game_name", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_play_sessions_ended_at"), "play_sessions", ["ended_at"], unique=False
    )
    op.create_index(
        op.f("ix_play_sessions_member_id"), "play_sessions", ["member_id"], unique=False
    )
    op.create_index(
        op.f("ix_play_sessions_started_at"),
        "play_sessions",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_play_sessions_steam_app_id"),
        "play_sessions",
        ["steam_app_id"],
        unique=False,
    )

    op.create_table(
        "presence_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("steam_app_id", sa.String(length=32), nullable=True),
        sa.Column("game_name", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_presence_segments_ended_at"),
        "presence_segments",
        ["ended_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_presence_segments_member_id"),
        "presence_segments",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_presence_segments_started_at"),
        "presence_segments",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_presence_segments_status"),
        "presence_segments",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_presence_segments_steam_app_id"),
        "presence_segments",
        ["steam_app_id"],
        unique=False,
    )

    op.create_table(
        "steam_friend_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("friend_steam_id", sa.String(length=32), nullable=False),
        sa.Column("friend_since", sa.Integer(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "friend_steam_id", name="uq_steam_friend_edge"),
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


def downgrade() -> None:
    op.drop_table("steam_friend_edges")
    op.drop_table("presence_segments")
    op.drop_table("play_sessions")
    op.drop_table("members")
    op.drop_table("system_configs")
    op.drop_table("register_challenges")
    op.drop_table("job_runs")
    op.drop_table("users")
