"""Add independent label coords for tarkov map places.

Revision ID: 20260901_0089
Revises: 20260901_0088
Create Date: 2026-09-01

MariaDB note: DDL is non-transactional; ADD COLUMN gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "20260901_0089"
down_revision: Union[str, Sequence[str], None] = "20260901_0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_map_places" not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns("tarkov_map_places")}
    if "label_x" not in cols:
        op.add_column("tarkov_map_places", sa.Column("label_x", sa.Float(), nullable=True))
    if "label_z" not in cols:
        op.add_column("tarkov_map_places", sa.Column("label_z", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())
    if "tarkov_map_places" not in tables:
        return
    cols = {c["name"] for c in sa_inspect(bind).get_columns("tarkov_map_places")}
    if "label_z" in cols:
        op.drop_column("tarkov_map_places", "label_z")
    if "label_x" in cols:
        op.drop_column("tarkov_map_places", "label_x")
