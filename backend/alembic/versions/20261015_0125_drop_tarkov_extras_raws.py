"""Drop tarkov_extras_raws.

Revision ID: 20261015_0125
Revises: 20261014_0124
Create Date: 2026-10-15

成就、声望、技能等目录留在 json.tarkov.dev 对应文件里，不再另存一份补集。

MariaDB note: DDL is non-transactional; DROP gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0125"
down_revision: Union[str, Sequence[str], None] = "20261014_0124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "tarkov_extras_raws"
_UQ = "uq_tarkov_extras_raws_mode_lang"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TABLE not in tables:
        return
    op.drop_table(_TABLE)


def downgrade() -> None:
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
