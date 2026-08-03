"""Widen arknights_box_snapshots.payload_json to LONGTEXT.

Revision ID: 20260804_0012
Revises: 20260804_0011
Create Date: 2026-08-04

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260804_0012"
down_revision: Union[str, Sequence[str], None] = "20260804_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE arknights_box_snapshots "
        "MODIFY COLUMN payload_json LONGTEXT NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE arknights_box_snapshots "
        "MODIFY COLUMN payload_json TEXT NOT NULL"
    )
