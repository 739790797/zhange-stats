"""Ensure arknights_box_snapshots exists with LONGTEXT payload.

Revision ID: 20260804_0012
Revises: 20260804_0011
Create Date: 2026-08-04

表可能仅由 create_all 建出；生产若尚未建表，直接 ALTER 会让启动失败。
本迁移幂等：无表则创建，有表则升级 payload_json 为 LONGTEXT。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260804_0012"
down_revision: Union[str, Sequence[str], None] = "20260804_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "arknights_box_snapshots" not in tables:
        op.create_table(
            "arknights_box_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("member_id", sa.Integer(), nullable=False),
            sa.Column("uid", sa.String(length=64), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("sync_date", sa.Date(), nullable=False),
            sa.Column(
                "synced_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["member_id"], ["members.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "member_id", "uid", name="uq_arknights_box_snapshot_member_uid"
            ),
        )
        op.create_index(
            "ix_arknights_box_snapshots_member_id",
            "arknights_box_snapshots",
            ["member_id"],
            unique=False,
        )
        op.create_index(
            "ix_arknights_box_snapshots_sync_date",
            "arknights_box_snapshots",
            ["sync_date"],
            unique=False,
        )

    op.execute(
        "ALTER TABLE arknights_box_snapshots "
        "MODIFY COLUMN payload_json LONGTEXT NOT NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "arknights_box_snapshots" not in tables:
        return
    op.execute(
        "ALTER TABLE arknights_box_snapshots "
        "MODIFY COLUMN payload_json TEXT NOT NULL"
    )
