"""Add members.qq_number for NapCat group matching.

Revision ID: 20260804_0016
Revises: 20260804_0015
Create Date: 2026-08-04

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0016"
down_revision: Union[str, Sequence[str], None] = "20260804_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("qq_number", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_members_qq_number", "members", ["qq_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_members_qq_number", table_name="members")
    op.drop_column("members", "qq_number")
