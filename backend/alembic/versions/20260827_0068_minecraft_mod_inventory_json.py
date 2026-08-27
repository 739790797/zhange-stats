"""Add minecraft_server_profiles.mod_inventory_json for on-disk jar inventory.

Revision ID: 20260827_0068
Revises: 20260826_0067
Create Date: 2026-08-27

MariaDB note: ``CAST('{}' AS JSON)`` is invalid on MariaDB (JSON is LONGTEXT).
Also MySQL/MariaDB DDL is non-transactional, so a failed fill after ADD leaves
the column present while alembic_version stays behind — upgrade must be idempotent.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260827_0068"
down_revision: Union[str, Sequence[str], None] = "20260826_0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {
        c["name"]: c for c in sa.inspect(bind).get_columns("minecraft_server_profiles")
    }
    if "mod_inventory_json" not in cols:
        op.add_column(
            "minecraft_server_profiles",
            sa.Column("mod_inventory_json", mysql.JSON(), nullable=True),
        )

    op.execute(
        "UPDATE minecraft_server_profiles "
        "SET mod_inventory_json = '{}' "
        "WHERE mod_inventory_json IS NULL"
    )

    cols = {
        c["name"]: c for c in sa.inspect(bind).get_columns("minecraft_server_profiles")
    }
    col = cols.get("mod_inventory_json")
    if col is not None and col.get("nullable", True):
        op.execute(
            "ALTER TABLE minecraft_server_profiles "
            "MODIFY COLUMN mod_inventory_json JSON NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("minecraft_server_profiles")}
    if "mod_inventory_json" in cols:
        op.drop_column("minecraft_server_profiles", "mod_inventory_json")
