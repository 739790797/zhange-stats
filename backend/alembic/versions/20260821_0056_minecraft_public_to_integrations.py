"""Move Minecraft public join address from playbook row into integrations.

Revision ID: 20260821_0056
Revises: 20260821_0055
Create Date: 2026-08-21

"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0056"
down_revision: Union[str, Sequence[str], None] = "20260821_0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_integrations(bind) -> tuple[object | None, dict]:
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
    return row, stored


def _write_integrations(bind, row, stored: dict) -> None:
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


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("minecraft_server_profiles")}
    if "public_host" not in cols and "public_port" not in cols:
        return

    if "public_host" in cols and "public_port" in cols:
        profile = bind.execute(
            sa.text(
                "SELECT public_host, public_port FROM minecraft_server_profiles WHERE id = 1"
            )
        ).mappings().first()
        if profile:
            host = (profile["public_host"] or "").strip()
            try:
                port = int(profile["public_port"] or 25565)
            except (TypeError, ValueError):
                port = 25565
            if port < 1 or port > 65535:
                port = 25565
            if host or port != 25565:
                row, stored = _load_integrations(bind)
                if host:
                    stored.setdefault("minecraft_public_host", host)
                stored.setdefault("minecraft_public_port", port)
                _write_integrations(bind, row, stored)

    if "public_port" in cols:
        op.drop_column("minecraft_server_profiles", "public_port")
    if "public_host" in cols:
        op.drop_column("minecraft_server_profiles", "public_host")


def downgrade() -> None:
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("public_host", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "minecraft_server_profiles",
        sa.Column("public_port", sa.Integer(), nullable=False, server_default="25565"),
    )
    bind = op.get_bind()
    _row, stored = _load_integrations(bind)
    host = str(stored.get("minecraft_public_host") or "").strip()
    try:
        port = int(stored.get("minecraft_public_port") or 25565)
    except (TypeError, ValueError):
        port = 25565
    if port < 1 or port > 65535:
        port = 25565
    if host or port != 25565:
        bind.execute(
            sa.text(
                "UPDATE minecraft_server_profiles "
                "SET public_host = :host, public_port = :port WHERE id = 1"
            ),
            {"host": host, "port": port},
        )
