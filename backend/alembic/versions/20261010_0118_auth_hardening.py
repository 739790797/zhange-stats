"""Auth hardening: users.token_version (JWT ver) and register_challenges.attempts.

Revision ID: 20261010_0118
Revises: 20260928_0117
Create Date: 2026-10-10

MariaDB note: DDL is non-transactional; each ADD COLUMN gated on inspect so a
half-applied upgrade can be re-run.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20261010_0118"
down_revision: Union[str, Sequence[str], None] = "20260928_0117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("users", "token_version"),
    ("register_challenges", "attempts"),
)


def _columns(bind, table: str) -> set[str] | None:
    if table not in set(sa_inspect(bind).get_table_names()):
        return None
    return {c["name"] for c in sa_inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in _COLUMNS:
        cols = _columns(bind, table)
        if cols is None or column in cols:
            continue
        op.add_column(
            table,
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table, column in reversed(_COLUMNS):
        cols = _columns(bind, table)
        if cols is None or column not in cols:
            continue
        op.drop_column(table, column)
