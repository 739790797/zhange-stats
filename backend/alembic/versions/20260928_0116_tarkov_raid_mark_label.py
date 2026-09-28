"""Add a label column for raid-room text marks.

Revision ID: 20260928_0116
Revises: 20260928_0115
Create Date: 2026-09-28

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260928_0116"
down_revision: Union[str, Sequence[str], None] = "20260928_0115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns("tarkov_raid_room_marks")}
    if "label" not in cols:
        op.add_column(
            "tarkov_raid_room_marks",
            sa.Column("label", sa.String(length=40), nullable=False, server_default=""),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_raid_room_marks" not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns("tarkov_raid_room_marks")}
    if "label" in cols:
        op.drop_column("tarkov_raid_room_marks", "label")
