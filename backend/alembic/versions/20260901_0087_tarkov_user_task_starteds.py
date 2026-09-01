"""Add tarkov user in-progress task ledger.

Revision ID: 20260901_0087
Revises: 20260831_0086
Create Date: 2026-09-01

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0087"
down_revision: Union[str, Sequence[str], None] = "20260831_0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_task_starteds" in tables:
        return
    op.create_table(
        "tarkov_user_task_starteds",
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
    if "tarkov_user_task_starteds" in tables:
        op.drop_table("tarkov_user_task_starteds")
