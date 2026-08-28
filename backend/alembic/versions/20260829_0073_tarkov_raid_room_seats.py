"""Tarkov raid rooms: wipe archives, five permanent seats, nullable host.

Revision ID: 20260829_0073
Revises: 20260829_0072
Create Date: 2026-08-29

MariaDB DDL is non-transactional; inspect before DROP/ALTER/INSERT.
First pass with old archive columns deletes all raid-room rows, then seeds 1–5.
Re-run skips the wipe so live seats are not cleared again.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0073"
down_revision: Union[str, Sequence[str], None] = "20260829_0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHILD_TABLES = (
    "tarkov_raid_room_marks",
    "tarkov_raid_room_key_brings",
    "tarkov_raid_room_task_claims",
    "tarkov_raid_room_members",
)
_DROP_INDEXES = (
    "ix_tarkov_raid_rooms_status_expire",
    "ix_tarkov_raid_rooms_status_created",
    "ix_tarkov_raid_rooms_status",
)
_DROP_COLUMNS = ("status", "expire_at", "archived_at")
_HOST_FK = "fk_tarkov_raid_rooms_host_user_id_users"


def _host_fks(bind) -> list[dict]:
    return [
        fk
        for fk in sa.inspect(bind).get_foreign_keys("tarkov_raid_rooms")
        if "host_user_id" in (fk.get("constrained_columns") or [])
    ]


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tarkov_raid_rooms" not in tables:
        return

    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_rooms")}
    wiping = bool(cols & set(_DROP_COLUMNS))
    if wiping:
        for table in _CHILD_TABLES:
            if table in tables:
                bind.execute(sa.text(f"DELETE FROM {table}"))
        bind.execute(sa.text("DELETE FROM tarkov_raid_rooms"))

    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("tarkov_raid_rooms")}
    for name in _DROP_INDEXES:
        if name in indexes:
            op.drop_index(name, table_name="tarkov_raid_rooms")

    cols = {c["name"] for c in sa.inspect(bind).get_columns("tarkov_raid_rooms")}
    for col in _DROP_COLUMNS:
        if col in cols:
            op.drop_column("tarkov_raid_rooms", col)

    for fk in _host_fks(bind):
        ondelete = str((fk.get("options") or {}).get("ondelete") or "").upper()
        name = fk.get("name")
        if ondelete == "SET NULL":
            continue
        if name:
            op.drop_constraint(name, "tarkov_raid_rooms", type_="foreignkey")

    host_col = next(
        (
            c
            for c in sa.inspect(bind).get_columns("tarkov_raid_rooms")
            if c["name"] == "host_user_id"
        ),
        None,
    )
    if host_col is not None and not host_col.get("nullable"):
        op.alter_column(
            "tarkov_raid_rooms",
            "host_user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    if not _host_fks(bind):
        op.create_foreign_key(
            _HOST_FK,
            "tarkov_raid_rooms",
            "users",
            ["host_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    existing = {
        str(row[0])
        for row in bind.execute(
            sa.text("SELECT public_id FROM tarkov_raid_rooms")
        ).fetchall()
    }
    for slot in range(1, 6):
        pid = str(slot)
        if pid in existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO tarkov_raid_rooms "
                "(public_id, title, map_slug, host_user_id, host_display_name, created_at) "
                "VALUES (:pid, :title, '', NULL, '', CURRENT_TIMESTAMP)"
            ),
            {"pid": pid, "title": f"{slot}号房"},
        )


def downgrade() -> None:
    """Seat rooms are not reversible without restoring archived rows."""
    return
