"""Add minecraft_server_profiles.mod_presets_json for draft mod presets.

Revision ID: 20260825_0064
Revises: 20260825_0063
Create Date: 2026-08-25

MariaDB note: ``CAST('{}' AS JSON)`` is invalid on MariaDB (JSON is LONGTEXT).
Also MySQL/MariaDB DDL is non-transactional, so a failed fill after ADD leaves
the column present while alembic_version stays behind — upgrade must be idempotent.
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
    bind = op.get_bind()
    cols = {
        c["name"]: c for c in sa.inspect(bind).get_columns("minecraft_server_profiles")
    }
    if "mod_presets_json" not in cols:
        op.add_column(
            "minecraft_server_profiles",
            sa.Column("mod_presets_json", mysql.JSON(), nullable=True),
        )

    # MariaDB rejects CAST(... AS JSON); assign a JSON text literal instead.
    op.execute(
        "UPDATE minecraft_server_profiles "
        "SET mod_presets_json = '{}' "
        "WHERE mod_presets_json IS NULL"
    )

    cols = {
        c["name"]: c for c in sa.inspect(bind).get_columns("minecraft_server_profiles")
    }
    col = cols.get("mod_presets_json")
    if col is not None and col.get("nullable", True):
        op.execute(
            "ALTER TABLE minecraft_server_profiles "
            "MODIFY COLUMN mod_presets_json JSON NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("minecraft_server_profiles")}
    if "mod_presets_json" in cols:
        op.drop_column("minecraft_server_profiles", "mod_presets_json")
