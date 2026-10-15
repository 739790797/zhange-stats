"""Add guide_raws for upstream guide documents.

Revision ID: 20261015_0126
Revises: 20261015_0125
Create Date: 2026-10-15

一个外部文件一行。雨中冒险 2 先用这张表；塔科夫仍用 tarkov_*_raws。

MariaDB note: DDL is non-transactional; CREATE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.sqltypes import LongText

revision: str = "20261015_0126"
down_revision: Union[str, Sequence[str], None] = "20261015_0125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "guide_raws"


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("game", sa.String(length=32), nullable=False),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("raw_body", LongText, nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("game", "resource", name="uq_guide_raws_game_resource"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in set(sa.inspect(bind).get_table_names()):
        return
    op.drop_table(_TABLE)
