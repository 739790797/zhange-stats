"""Unify tarkov ammo/gun raw into shared items raw.

Revision ID: 20260812_0040
Revises: 20260812_0039
Create Date: 2026-08-12

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0040"
down_revision: Union[str, Sequence[str], None] = "20260812_0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tarkov_items_raws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tarkov_items_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("ammo_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gun_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    conn = op.get_bind()
    # Prefer gun raw (json items dump) over ammo-only raw when migrating.
    gun = conn.execute(
        sa.text(
            "SELECT id, source, raw_json, synced_at, note FROM tarkov_gun_raws WHERE id = 1"
        )
    ).fetchone()
    ammo = conn.execute(
        sa.text(
            "SELECT id, source, raw_json, synced_at, note FROM tarkov_ammo_raws WHERE id = 1"
        )
    ).fetchone()
    chosen = gun or ammo
    if chosen is not None:
        conn.execute(
            sa.text(
                "INSERT INTO tarkov_items_raws (id, source, raw_json, synced_at, note) "
                "VALUES (1, :source, :raw_json, :synced_at, :note)"
            ),
            {
                "source": chosen.source,
                "raw_json": chosen.raw_json,
                "synced_at": chosen.synced_at,
                "note": chosen.note,
            },
        )
        ammo_count = conn.execute(sa.text("SELECT COUNT(*) FROM tarkov_ammo")).scalar() or 0
        gun_count = conn.execute(sa.text("SELECT COUNT(*) FROM tarkov_guns")).scalar() or 0
        conn.execute(
            sa.text(
                "INSERT INTO tarkov_items_meta "
                "(id, source, ammo_count, gun_count, synced_at, note) "
                "VALUES (1, :source, :ammo_count, :gun_count, :synced_at, :note)"
            ),
            {
                "source": chosen.source,
                "ammo_count": int(ammo_count),
                "gun_count": int(gun_count),
                "synced_at": chosen.synced_at,
                "note": chosen.note,
            },
        )

    op.drop_table("tarkov_gun_raws")
    op.drop_table("tarkov_ammo_raws")


def downgrade() -> None:
    op.create_table(
        "tarkov_ammo_raws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tarkov_gun_raws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    conn = op.get_bind()
    items = conn.execute(
        sa.text(
            "SELECT id, source, raw_json, synced_at, note FROM tarkov_items_raws WHERE id = 1"
        )
    ).fetchone()
    if items is not None:
        for table in ("tarkov_ammo_raws", "tarkov_gun_raws"):
            conn.execute(
                sa.text(
                    f"INSERT INTO {table} (id, source, raw_json, synced_at, note) "
                    "VALUES (1, :source, :raw_json, :synced_at, :note)"
                ),
                {
                    "source": items.source,
                    "raw_json": items.raw_json,
                    "synced_at": items.synced_at,
                    "note": items.note,
                },
            )
    op.drop_table("tarkov_items_meta")
    op.drop_table("tarkov_items_raws")
