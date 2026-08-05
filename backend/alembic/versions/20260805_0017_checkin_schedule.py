"""Add per-user checkin hour/minute on platform binds.

Revision ID: 20260805_0017
Revises: 20260804_0016
Create Date: 2026-08-05

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0017"
down_revision: Union[str, Sequence[str], None] = "20260804_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "skland_binds",
    "taygedo_binds",
    "exilium_binds",
    "kujiequ_binds",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "checkin_hour",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "checkin_minute",
                sa.Integer(),
                nullable=False,
                server_default="5",
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "checkin_minute")
        op.drop_column(table, "checkin_hour")
