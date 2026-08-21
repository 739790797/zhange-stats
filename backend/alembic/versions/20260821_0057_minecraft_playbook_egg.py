"""Store Minecraft playbook egg and startup on the draft row.

Revision ID: 20260821_0057
Revises: 20260821_0056
Create Date: 2026-08-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0057"
down_revision: Union[str, Sequence[str], None] = "20260821_0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("minecraft_server_profiles")}
    if "egg_id" not in cols:
        op.add_column(
            "minecraft_server_profiles",
            sa.Column("egg_id", sa.Integer(), nullable=False, server_default="0"),
        )
    if "startup" not in cols:
        op.add_column(
            "minecraft_server_profiles",
            sa.Column("startup", sa.Text(), nullable=True),
        )
        op.execute("UPDATE minecraft_server_profiles SET startup = '' WHERE startup IS NULL")
        op.alter_column(
            "minecraft_server_profiles",
            "startup",
            existing_type=sa.Text(),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("minecraft_server_profiles")}
    if "startup" in cols:
        op.drop_column("minecraft_server_profiles", "startup")
    if "egg_id" in cols:
        op.drop_column("minecraft_server_profiles", "egg_id")
