"""Move Minecraft RCON credentials from playbook row into integrations secrets.

Revision ID: 20260821_0054
Revises: 20260821_0053
Create Date: 2026-08-21

"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0054"
down_revision: Union[str, Sequence[str], None] = "20260821_0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    profile = bind.execute(
        sa.text(
            "SELECT rcon_connect_host, rcon_port, rcon_connect_port, "
            "rcon_password_enc, public_host "
            "FROM minecraft_server_profiles WHERE id = 1"
        )
    ).mappings().first()
    if profile:
        host = (profile["rcon_connect_host"] or "").strip() or (
            profile["public_host"] or ""
        ).strip()
        mapped = int(profile["rcon_connect_port"] or 0)
        listen = int(profile["rcon_port"] or 25575)
        port = mapped if 1 <= mapped <= 65535 else listen
        if port < 1 or port > 65535:
            port = 25575
        password_enc = (profile["rcon_password_enc"] or "").strip()
        if host or password_enc:
            row = bind.execute(
                sa.text("SELECT value FROM system_configs WHERE `key` = 'integrations'")
            ).mappings().first()
            stored: dict = {}
            if row:
                try:
                    parsed = json.loads(row["value"] or "{}")
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict):
                    stored = parsed
            if host:
                stored.setdefault("minecraft_rcon_host", host)
            stored.setdefault("minecraft_rcon_port", port)
            if password_enc:
                stored.setdefault("minecraft_rcon_password", password_enc)
            payload = json.dumps(stored, ensure_ascii=False)
            if row:
                bind.execute(
                    sa.text(
                        "UPDATE system_configs SET value = :v WHERE `key` = 'integrations'"
                    ),
                    {"v": payload},
                )
            else:
                bind.execute(
                    sa.text(
                        "INSERT INTO system_configs (`key`, value) VALUES ('integrations', :v)"
                    ),
                    {"v": payload},
                )

    op.drop_column("minecraft_server_profiles", "rcon_password_enc")
    op.drop_column("minecraft_server_profiles", "rcon_connect_port")
    op.drop_column("minecraft_server_profiles", "rcon_connect_host")
    op.drop_column("minecraft_server_profiles", "rcon_port")
    op.drop_column("minecraft_server_profiles", "rcon_enabled")


def downgrade() -> None:
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
