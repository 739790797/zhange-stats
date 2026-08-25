"""Drop members.qq_number and NapCat keys from integrations JSON.

Revision ID: 20260825_0065
Revises: 20260825_0064
Create Date: 2026-08-25

MySQL/MariaDB DDL is non-transactional, so upgrade must be idempotent.
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0065"
down_revision: Union[str, Sequence[str], None] = "20260825_0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {ix["name"] for ix in inspector.get_indexes("members")}
    cols = {c["name"] for c in inspector.get_columns("members")}
    if "ix_members_qq_number" in indexes:
        op.drop_index("ix_members_qq_number", table_name="members")
    if "qq_number" in cols:
        op.drop_column("members", "qq_number")

    row = bind.execute(
        sa.text("SELECT value FROM system_configs WHERE `key` = 'integrations'")
    ).mappings().first()
    if not row:
        return
    try:
        stored = json.loads(row["value"] or "{}")
    except json.JSONDecodeError:
        return
    if not isinstance(stored, dict):
        return
    stored.pop("napcat_base_url", None)
    stored.pop("napcat_token", None)
    bind.execute(
        sa.text("UPDATE system_configs SET value = :v WHERE `key` = 'integrations'"),
        {"v": json.dumps(stored, ensure_ascii=False)},
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("members")}
    indexes = {ix["name"] for ix in inspector.get_indexes("members")}
    if "qq_number" not in cols:
        op.add_column(
            "members",
            sa.Column("qq_number", sa.String(length=20), nullable=True),
        )
    if "ix_members_qq_number" not in indexes:
        op.create_index("ix_members_qq_number", "members", ["qq_number"], unique=True)
