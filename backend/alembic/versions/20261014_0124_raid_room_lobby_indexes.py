"""Raid room lobby / seat indexes.

Revision ID: 20261014_0124
Revises: 20261013_0123
Create Date: 2026-10-14

tarkov_raid_rooms: drop ix_tarkov_raid_rooms_map_slug. The column has been kept but always "",
so the index is pure write cost and no query can use it.

tarkov_raid_rooms: add (listed, game_mode, created_at) for the lobby page query
(`listed` + current mode, ordered by created_at desc).

tarkov_raid_room_members: add last_seen_at for the idle-seat reclaim scan
(`last_seen_at < cutoff` across all rooms).

MariaDB note: DDL is non-transactional; every step is gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0124"
down_revision: Union[str, Sequence[str], None] = "20261013_0123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROOMS = "tarkov_raid_rooms"
_MEMBERS = "tarkov_raid_room_members"
_DROP_INDEX = "ix_tarkov_raid_rooms_map_slug"
_LOBBY_INDEX = "ix_tarkov_raid_rooms_lobby"
_LAST_SEEN_INDEX = "ix_tarkov_raid_room_members_last_seen_at"


def _indexes(bind, table: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _ROOMS in tables:
        indexes = _indexes(bind, _ROOMS)
        if _DROP_INDEX in indexes:
            op.drop_index(_DROP_INDEX, table_name=_ROOMS)
        if _LOBBY_INDEX not in indexes:
            op.create_index(
                _LOBBY_INDEX,
                _ROOMS,
                ["listed", "game_mode", "created_at"],
            )
    if _MEMBERS in tables:
        if _LAST_SEEN_INDEX not in _indexes(bind, _MEMBERS):
            op.create_index(_LAST_SEEN_INDEX, _MEMBERS, ["last_seen_at"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _ROOMS in tables:
        indexes = _indexes(bind, _ROOMS)
        if _LOBBY_INDEX in indexes:
            op.drop_index(_LOBBY_INDEX, table_name=_ROOMS)
        if _DROP_INDEX not in indexes:
            op.create_index(_DROP_INDEX, _ROOMS, ["map_slug"])
    if _MEMBERS in tables:
        if _LAST_SEEN_INDEX in _indexes(bind, _MEMBERS):
            op.drop_index(_LAST_SEEN_INDEX, table_name=_MEMBERS)
