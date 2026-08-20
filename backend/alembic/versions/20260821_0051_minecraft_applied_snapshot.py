"""Store last-applied Minecraft playbook snapshot.

Revision ID: 20260821_0051
Revises: 20260820_0050
Create Date: 2026-08-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260821_0051"
down_revision: Union[str, Sequence[str], None] = "20260820_0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("applied_json", mysql.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("minecraft_server_profiles", "applied_json")
