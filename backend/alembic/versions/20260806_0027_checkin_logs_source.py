"""Add source column to checkin logs (status vs action).

Revision ID: 20260806_0027
Revises: 20260806_0026
Create Date: 2026-08-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0027"
down_revision: Union[str, Sequence[str], None] = "20260806_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "skland_checkin_logs",
    "taygedo_checkin_logs",
    "exilium_checkin_logs",
    "kujiequ_checkin_logs",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "source",
                sa.String(length=16),
                nullable=False,
                server_default="status",
            ),
        )
        # 历史行无法区分查询/执行；统一标为 status，避免「同步结果」出现在执行记录
        op.execute(sa.text(f"UPDATE `{table}` SET source='status'"))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "source")
