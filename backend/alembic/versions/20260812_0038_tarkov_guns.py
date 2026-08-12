"""Add tarkov gun catalog tables (raw + derived + meta).

Revision ID: 20260812_0038
Revises: 20260812_0037
Create Date: 2026-08-12

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0038"
down_revision: Union[str, Sequence[str], None] = "20260812_0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tarkov_gun_raws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tarkov_guns",
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("short_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("caliber", sa.String(length=64), nullable=False),
        sa.Column("weapon_class", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("fire_rate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ergonomics", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recoil_vertical", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recoil_horizontal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_distance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fire_modes_json", sa.Text(), nullable=False),
        sa.Column("default_ammo_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("allowed_ammo_json", sa.Text(), nullable=False),
        sa.Column("icon_link", sa.String(length=512), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index("ix_tarkov_guns_caliber", "tarkov_guns", ["caliber"], unique=False)
    op.create_index(
        "ix_tarkov_guns_weapon_class", "tarkov_guns", ["weapon_class"], unique=False
    )
    op.create_table(
        "tarkov_gun_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("gun_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("tarkov_gun_meta")
    op.drop_index("ix_tarkov_guns_weapon_class", table_name="tarkov_guns")
    op.drop_index("ix_tarkov_guns_caliber", table_name="tarkov_guns")
    op.drop_table("tarkov_guns")
    op.drop_table("tarkov_gun_raws")
