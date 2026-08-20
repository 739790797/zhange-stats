"""Minecraft profile RCON connection settings.

Revision ID: 20260821_0052
Revises: 20260821_0051
Create Date: 2026-08-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0052"
down_revision: Union[str, Sequence[str], None] = "20260821_0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("rcon_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("rcon_port", sa.Integer(), nullable=False, server_default="25575"),
    )
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("rcon_connect_host", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("rcon_connect_port", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("rcon_password_enc", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("minecraft_server_profiles", "rcon_password_enc")
    op.drop_column("minecraft_server_profiles", "rcon_connect_port")
    op.drop_column("minecraft_server_profiles", "rcon_connect_host")
    op.drop_column("minecraft_server_profiles", "rcon_port")
    op.drop_column("minecraft_server_profiles", "rcon_enabled")
