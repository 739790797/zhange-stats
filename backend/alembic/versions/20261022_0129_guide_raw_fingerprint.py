"""Add a content fingerprint to cached guide source documents.

Revision ID: 20261022_0129
Revises: 20261022_0128
Create Date: 2026-10-22

Existing rows are backfilled lazily during the next successful raw sync.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0129"
down_revision: Union[str, Sequence[str], None] = "20261022_0128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "guide_raws"
_COLUMN = "content_fingerprint"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TABLE not in tables:
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns(_TABLE)}
    if _COLUMN not in columns:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TABLE not in tables:
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns(_TABLE)}
    if _COLUMN in columns:
        op.drop_column(_TABLE, _COLUMN)
