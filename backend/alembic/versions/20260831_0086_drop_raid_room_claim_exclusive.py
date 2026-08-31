"""Drop raid room task claim exclusive flag.

Revision ID: 20260831_0086
Revises: 20260831_0085
Create Date: 2026-08-31

MariaDB DDL is non-transactional; DROP COLUMN gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0086"
down_revision: Union[str, Sequence[str], None] = "20260831_0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_room_task_claims" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_room_task_claims")}
    if "exclusive" in cols:
        op.drop_column("tarkov_raid_room_task_claims", "exclusive")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tarkov_raid_room_task_claims" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("tarkov_raid_room_task_claims")}
    if "exclusive" not in cols:
        op.add_column(
            "tarkov_raid_room_task_claims",
            sa.Column(
                "exclusive",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
