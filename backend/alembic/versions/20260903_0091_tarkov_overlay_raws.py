"""Add tarkov overlay raw table for tarkov-data-overlay.

Revision ID: 20260903_0091
Revises: 20260901_0090
Create Date: 2026-09-03

MariaDB: CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0091"
down_revision: Union[str, Sequence[str], None] = "20260901_0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "tarkov_overlay_raws"
_UQ = "uq_tarkov_overlay_raws_mode_lang"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TABLE in tables:
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mode_id", sa.Integer(), nullable=False),
        sa.Column("lang", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode_id", "lang", name=_UQ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TABLE not in tables:
        return
    op.drop_table(_TABLE)
