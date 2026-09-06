"""Add personal raid-prep route JSON.

Revision ID: 20260906_0097
Revises: 20260905_0096
Create Date: 2026-09-06

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
JSON columns cannot use DEFAULT; app writes [].
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260906_0097"
down_revision: Union[str, Sequence[str], None] = "20260905_0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_user_raid_preps" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_user_raid_preps")}
    if "route_json" in cols:
        return
    op.add_column(
        "tarkov_user_raid_preps",
        sa.Column("route_json", mysql.JSON(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tarkov_user_raid_preps" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_user_raid_preps")}
    if "route_json" not in cols:
        return
    op.drop_column("tarkov_user_raid_preps", "route_json")
