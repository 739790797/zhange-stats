"""Server-side boundary for the Tarkov task ledger.

Revision ID: 20261013_0123
Revises: 20261010_0122
Create Date: 2026-10-13

tarkov_user_task_resets: one row per (user, game_mode). reset_at only moves forward. Game-log
replay must not write back any quest event older than it, so "清空进度" / prestige survive logout,
other browsers and the assistant WebView (the boundary used to live only in localStorage).
pending_clear_at is User clear that no device with game logs has resolved into User boundary yet.
epoch goes up on every clear / boundary move; bulk writes carrying an older epoch get 409.

tarkov_user_task_cleareds: tasks the user moved out of "done" by hand, with the time; an older
completion in the logs must not stick them back.

MariaDB note: DDL is non-transactional; each CREATE TABLE is gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_0123"
down_revision: Union[str, Sequence[str], None] = "20261010_0122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RESETS = "tarkov_user_task_resets"
_CLEAREDS = "tarkov_user_task_cleareds"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if _RESETS not in tables:
        op.create_table(
            _RESETS,
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("game_mode", sa.String(length=8), nullable=False),
            sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("pending_clear_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("profile_id", sa.String(length=64), nullable=False),
            sa.Column("reason", sa.String(length=16), nullable=False),
            sa.Column("epoch", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "game_mode"),
        )
    if _CLEAREDS not in tables:
        op.create_table(
            _CLEAREDS,
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("game_mode", sa.String(length=8), nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "game_mode", "task_id"),
        )


def downgrade() -> None:
    tables = _tables()
    if _CLEAREDS in tables:
        op.drop_table(_CLEAREDS)
    if _RESETS in tables:
        op.drop_table(_RESETS)
