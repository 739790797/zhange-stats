"""Purge logically deleted articles; delete is now physical.

Revision ID: 20260908_0105
Revises: 20260907_0104
Create Date: 2026-09-08

Idempotent: DELETE WHERE status='deleted' is a no-op after the first run.
Child rows follow ON DELETE CASCADE (comments / versions / term links).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0105"
down_revision: Union[str, Sequence[str], None] = "20260907_0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "articles" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("articles")}
    if "status" not in cols:
        return
    op.execute(sa.text("DELETE FROM articles WHERE status = 'deleted'"))


def downgrade() -> None:
    pass
