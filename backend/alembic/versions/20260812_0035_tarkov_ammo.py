"""Add tarkov ammo catalog tables.

Revision ID: 20260812_0035
Revises: 20260811_0034
Create Date: 2026-08-12

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0035"
down_revision: Union[str, Sequence[str], None] = "20260811_0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tarkov_ammo",
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("short_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("caliber", sa.String(length=64), nullable=False),
        sa.Column("damage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("penetration", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("armor_damage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index("ix_tarkov_ammo_caliber", "tarkov_ammo", ["caliber"], unique=False)

    op.create_table(
        "tarkov_ammo_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("ammo_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("tarkov_ammo_meta")
    op.drop_index("ix_tarkov_ammo_caliber", table_name="tarkov_ammo")
    op.drop_table("tarkov_ammo")
