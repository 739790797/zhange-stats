"""Remember Steam store / client-icon lookups that found nothing.

Revision ID: 20261010_0122
Revises: 20261010_0121
Create Date: 2026-10-10

steam_apps.details_missed_at / icon_missed_at hold the last time the store appdetails call or the
client-icon backfill (GetOwnedGames + steamcmd) came back empty, so the icon and store-card
endpoints stop going upstream for the same app until the retry window passes. Nullable, no
default: existing rows simply have no recorded miss.

MariaDB note: DDL is non-transactional; each ADD COLUMN is gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0122"
down_revision: Union[str, Sequence[str], None] = "20261010_0121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "steam_apps"
_COLUMNS = ("details_missed_at", "icon_missed_at")


def _existing_columns() -> set[str] | None:
    insp = sa.inspect(op.get_bind())
    if _TABLE not in set(insp.get_table_names()):
        return None
    return {c["name"] for c in insp.get_columns(_TABLE)}


def upgrade() -> None:
    cols = _existing_columns()
    if cols is None:
        return
    for name in _COLUMNS:
        if name not in cols:
            op.add_column(_TABLE, sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    cols = _existing_columns()
    if cols is None:
        return
    for name in _COLUMNS:
        if name in cols:
            op.drop_column(_TABLE, name)
