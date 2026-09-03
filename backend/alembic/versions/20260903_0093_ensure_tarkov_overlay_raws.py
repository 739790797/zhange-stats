"""Ensure tarkov overlay raw table exists.

Revision ID: 20260903_0093
Revises: 20260903_0092
Create Date: 2026-09-03

0091 already creates this table. Some local DBs stamped past 0091 after a
revision-id collision (objective-dones briefly reused 0091), so overlay
never got created. CREATE is gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0093"
down_revision: Union[str, Sequence[str], None] = "20260903_0092"
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
    # 0091 owns the real drop; this revision only repairs a skipped create.
    return
