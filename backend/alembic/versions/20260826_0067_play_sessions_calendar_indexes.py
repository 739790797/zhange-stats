"""Play session calendar indexes: source+started_at, last_seen_at.

Revision ID: 20260826_0067
Revises: 20260826_0066
Create Date: 2026-08-26

MySQL/MariaDB DDL is non-transactional, so upgrade must be idempotent.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0067"
down_revision: Union[str, Sequence[str], None] = "20260826_0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {ix["name"] for ix in inspector.get_indexes(table) if ix.get("name")}


def _create_index(name: str, table: str, cols: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    if name in _index_names(table):
        return
    op.create_index(name, table, cols, unique=False)


def _drop_index(table: str, name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    if name not in _index_names(table):
        return
    op.drop_index(name, table_name=table)


def upgrade() -> None:
    _create_index(
        "ix_play_sessions_source_started",
        "play_sessions",
        ["source", "started_at"],
    )
    _create_index("ix_play_sessions_last_seen_at", "play_sessions", ["last_seen_at"])


def downgrade() -> None:
    _drop_index("play_sessions", "ix_play_sessions_last_seen_at")
    _drop_index("play_sessions", "ix_play_sessions_source_started")
