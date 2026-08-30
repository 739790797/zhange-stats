"""Add tarkov user task completion.

Revision ID: 20260830_0081
Revises: 20260830_0080
Create Date: 2026-08-30

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0081"
down_revision: Union[str, Sequence[str], None] = "20260830_0080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_task_dones" in tables:
        return
    op.create_table(
        "tarkov_user_task_dones",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_mode", sa.String(length=8), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "game_mode", "task_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_task_dones" in tables:
        op.drop_table("tarkov_user_task_dones")
