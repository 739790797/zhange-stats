"""Add members.steam_avatar_url for Steam-only avatar.

Revision ID: 20260804_0015
Revises: 20260804_0014
Create Date: 2026-08-04

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0015"
down_revision: Union[str, Sequence[str], None] = "20260804_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("steam_avatar_url", sa.String(length=512), nullable=True),
    )
    # 已绑 Steam 的存量：把当前头像视为 Steam 头像副本（站内头像仍保留可改）
    op.execute(
        sa.text(
            "UPDATE members SET steam_avatar_url = avatar_url "
            "WHERE steam_id IS NOT NULL AND avatar_url IS NOT NULL "
            "AND steam_avatar_url IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("members", "steam_avatar_url")
