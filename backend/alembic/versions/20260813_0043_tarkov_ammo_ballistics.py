"""Add tarkov_ammo ballistics modifier columns.

Revision ID: 20260813_0043
Revises: 20260812_0042
Create Date: 2026-08-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0043"
down_revision: Union[str, Sequence[str], None] = "20260812_0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tarkov_ammo",
        sa.Column(
            "initial_speed",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "tarkov_ammo",
        sa.Column(
            "accuracy_modifier",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "tarkov_ammo",
        sa.Column(
            "recoil_modifier",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "tarkov_ammo",
        sa.Column(
            "light_bleed_modifier",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "tarkov_ammo",
        sa.Column(
            "heavy_bleed_modifier",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("tarkov_ammo", "heavy_bleed_modifier")
    op.drop_column("tarkov_ammo", "light_bleed_modifier")
    op.drop_column("tarkov_ammo", "recoil_modifier")
    op.drop_column("tarkov_ammo", "accuracy_modifier")
    op.drop_column("tarkov_ammo", "initial_speed")
