"""Opt-in flags default to 0 in the database as well.

Revision ID: 20261010_0121
Revises: 20261010_0119
Create Date: 2026-10-10

checkin_role_prefs.included (0029) and the skland / taygedo / exilium / kujiequ auto_checkin
flags (0007 / 0008 / 0011 / 0013) were added with DEFAULT 1 so the rows existing back then kept
their behaviour. The app has written False for every new row since (models: default=False), so a
raw INSERT that omits the column must not opt the row in either. Only the default changes; stored
values stay as they are.

A column without a DB default (SQLite files built by create_all) is left alone: an INSERT that
omits it fails on NOT NULL instead of opting in. MariaDB gets ALTER COLUMN ... SET DEFAULT, which
is metadata only; SQLite would need a batch rebuild, done only where a default of 1 is found.
Downgrade is a no-op: DEFAULT 1 only mattered for the backfill those migrations already did.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0121"
down_revision: Union[str, Sequence[str], None] = "20261010_0119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OPT_IN_FLAGS = (
    ("checkin_role_prefs", "included"),
    ("skland_binds", "auto_checkin"),
    ("taygedo_binds", "auto_checkin"),
    ("exilium_binds", "auto_checkin"),
    ("kujiequ_binds", "auto_checkin"),
)


def _defaults_to_true(default: object) -> bool:
    text = str(default or "").strip()
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    return text.strip("'").lower() in ("1", "true")


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for table, column in _OPT_IN_FLAGS:
        if table not in tables:
            continue
        info = next((c for c in insp.get_columns(table) if c["name"] == column), None)
        if info is None or not _defaults_to_true(info.get("default")):
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                existing_type=sa.Boolean(),
                existing_nullable=bool(info.get("nullable")),
                server_default=sa.text("0"),
            )


def downgrade() -> None:
    pass
