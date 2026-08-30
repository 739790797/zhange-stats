"""Add tarkov user raid log summaries.

Revision ID: 20260830_0077
Revises: 20260830_0076
Create Date: 2026-08-30

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0077"
down_revision: Union[str, Sequence[str], None] = "20260830_0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_raid_logs" in tables:
        return
    op.create_table(
        "tarkov_user_raid_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=220), nullable=False),
        sa.Column("folder", sa.String(length=128), nullable=False),
        sa.Column("raid_id", sa.String(length=16), nullable=False),
        sa.Column("location", sa.String(length=64), nullable=False),
        sa.Column("map_id", sa.String(length=32), nullable=False),
        sa.Column("map_label", sa.String(length=32), nullable=False),
        sa.Column("raid_mode", sa.String(length=16), nullable=False),
        sa.Column("session_mode", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.String(length=32), nullable=False),
        sa.Column("ended_at", sa.String(length=32), nullable=False),
        sa.Column("reconnected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("aborted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "dedupe_key",
            name="uq_tarkov_user_raid_logs_user_dedupe",
        ),
    )
    op.create_index(
        "ix_tarkov_user_raid_logs_user_started",
        "tarkov_user_raid_logs",
        ["user_id", "started_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_raid_logs" not in tables:
        return
    op.drop_index(
        "ix_tarkov_user_raid_logs_user_started",
        table_name="tarkov_user_raid_logs",
    )
    op.drop_table("tarkov_user_raid_logs")
