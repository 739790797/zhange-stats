"""Add tarkov user collection layout save markers.

Revision ID: 20260905_0096
Revises: 20260905_0095
Create Date: 2026-09-05

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0096"
down_revision: Union[str, Sequence[str], None] = "20260905_0095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_collection_layouts" not in tables:
        op.create_table(
            "tarkov_user_collection_layouts",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("game_mode", sa.String(length=8), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "game_mode"),
        )
    if "tarkov_user_collection_placements" not in tables:
        return
    op.execute(
        sa.text(
            """
            INSERT INTO tarkov_user_collection_layouts (user_id, game_mode, updated_at)
            SELECT p.user_id, p.game_mode, CURRENT_TIMESTAMP
            FROM (
                SELECT DISTINCT user_id, game_mode
                FROM tarkov_user_collection_placements
            ) AS p
            LEFT JOIN tarkov_user_collection_layouts AS m
              ON m.user_id = p.user_id AND m.game_mode = p.game_mode
            WHERE m.user_id IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_user_collection_layouts" in tables:
        op.drop_table("tarkov_user_collection_layouts")
