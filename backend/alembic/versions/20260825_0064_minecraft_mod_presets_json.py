"""Add minecraft_server_profiles.mod_presets_json for draft mod presets.

Revision ID: 20260825_0064
Revises: 20260825_0063
Create Date: 2026-08-25

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260825_0064"
down_revision: Union[str, Sequence[str], None] = "20260825_0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("mod_presets_json", mysql.JSON(), nullable=True),
    )
    op.execute(
        "UPDATE minecraft_server_profiles "
        "SET mod_presets_json = CAST('{}' AS JSON) "
        "WHERE mod_presets_json IS NULL"
    )
    op.alter_column(
        "minecraft_server_profiles",
        "mod_presets_json",
        existing_type=mysql.JSON(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("minecraft_server_profiles", "mod_presets_json")
