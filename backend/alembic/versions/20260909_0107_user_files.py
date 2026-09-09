"""Add user_files registry for user uploads (serial + relative path).

Revision ID: 20260909_0107
Revises: 20260908_0106
Create Date: 2026-09-09

MariaDB note: DDL is non-transactional; CREATE TABLE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0107"
down_revision: Union[str, Sequence[str], None] = "20260908_0106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "user_files" in tables:
        return
    op.create_table(
        "user_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("serial", sa.String(length=32), nullable=False),
        sa.Column("namespace", sa.String(length=32), nullable=False),
        sa.Column("rel_path", sa.String(length=512), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial", name="uq_user_files_serial"),
        sa.UniqueConstraint("rel_path", name="uq_user_files_rel_path"),
    )
    op.create_index("ix_user_files_namespace", "user_files", ["namespace"])
    op.create_index("ix_user_files_owner_user_id", "user_files", ["owner_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "user_files" not in tables:
        return
    op.drop_index("ix_user_files_owner_user_id", table_name="user_files")
    op.drop_index("ix_user_files_namespace", table_name="user_files")
    op.drop_table("user_files")
