"""Add arknights operator catalog tables.

Revision ID: 20260803_0010
Revises: 20260803_0009
Create Date: 2026-08-03

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0010"
down_revision: Union[str, Sequence[str], None] = "20260803_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "arknights_operators",
        sa.Column("char_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("profession", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "profession_label", sa.String(length=16), nullable=False, server_default=""
        ),
        sa.Column("sort_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("char_id"),
    )
    op.create_index(
        "ix_arknights_operators_rarity", "arknights_operators", ["rarity"], unique=False
    )
    op.create_index(
        "ix_arknights_operators_profession",
        "arknights_operators",
        ["profession"],
        unique=False,
    )

    op.create_table(
        "arknights_catalog_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("operator_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("arknights_catalog_meta")
    op.drop_index("ix_arknights_operators_profession", table_name="arknights_operators")
    op.drop_index("ix_arknights_operators_rarity", table_name="arknights_operators")
    op.drop_table("arknights_operators")
