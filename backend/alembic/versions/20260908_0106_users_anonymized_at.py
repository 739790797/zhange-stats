"""Add users.anonymized_at for account deletion (keep row, wipe identity).

Revision ID: 20260908_0106
Revises: 20260908_0105
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0106"
down_revision: Union[str, Sequence[str], None] = "20260908_0105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "anonymized_at" in cols:
        return
    op.add_column(
        "users",
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "anonymized_at" not in cols:
        return
    op.drop_column("users", "anonymized_at")
