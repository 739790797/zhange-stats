"""Add minecraft_server_profiles (single-row desired state).

Revision ID: 20260820_0050
Revises: 20260814_0049
Create Date: 2026-08-20

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260820_0050"
down_revision: Union[str, Sequence[str], None] = "20260814_0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "minecraft_server_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mc_version", sa.String(length=32), nullable=False, server_default="1.21.1"),
        sa.Column("loader", sa.String(length=32), nullable=False, server_default="fabric"),
        sa.Column("loader_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("mods_json", mysql.JSON(), nullable=False),
        sa.Column("overrides_json", mysql.JSON(), nullable=False),
        sa.Column("public_host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("public_port", sa.Integer(), nullable=False, server_default="25565"),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_apply_message", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("minecraft_server_profiles")
