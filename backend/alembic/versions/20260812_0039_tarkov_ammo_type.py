"""Add tarkov_ammo.ammo_type from upstream.

Revision ID: 20260812_0039
Revises: 20260812_0038
Create Date: 2026-08-12

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0039"
down_revision: Union[str, Sequence[str], None] = "20260812_0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tarkov_ammo",
        sa.Column(
            "ammo_type",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index("ix_tarkov_ammo_ammo_type", "tarkov_ammo", ["ammo_type"])


def downgrade() -> None:
    op.drop_index("ix_tarkov_ammo_ammo_type", table_name="tarkov_ammo")
    op.drop_column("tarkov_ammo", "ammo_type")
