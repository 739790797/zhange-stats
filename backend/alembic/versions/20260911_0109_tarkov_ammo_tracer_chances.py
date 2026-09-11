"""Add tarkov_ammo tracer / fragmentation / ricochet columns.

Revision ID: 20260911_0109
Revises: 20260909_0108
Create Date: 2026-09-11

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260911_0109"
down_revision: Union[str, Sequence[str], None] = "20260909_0108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "tarkov_ammo"
_COLUMNS = (
    ("tracer", sa.Column("tracer", sa.Boolean(), nullable=False, server_default=sa.false())),
    ("tracer_color", sa.Column("tracer_color", sa.String(length=32), nullable=False, server_default="")),
    (
        "fragmentation_chance",
        sa.Column("fragmentation_chance", sa.Float(), nullable=False, server_default="0"),
    ),
    (
        "ricochet_chance",
        sa.Column("ricochet_chance", sa.Float(), nullable=False, server_default="0"),
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if _TABLE not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns(_TABLE)}
    for name, column in _COLUMNS:
        if name not in cols:
            op.add_column(_TABLE, column)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if _TABLE not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns(_TABLE)}
    for name, _column in reversed(_COLUMNS):
        if name in cols:
            op.drop_column(_TABLE, name)
