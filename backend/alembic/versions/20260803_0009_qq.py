"""Add QQ bind columns on members.

Revision ID: 20260803_0009
Revises: 20260803_0008
Create Date: 2026-08-03

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0009"
down_revision: Union[str, Sequence[str], None] = "20260803_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("qq_openid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "members",
        sa.Column("qq_unionid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "members",
        sa.Column("qq_nickname", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "members",
        sa.Column("qq_avatar_url", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_members_qq_openid", "members", ["qq_openid"], unique=True)
    op.create_index("ix_members_qq_unionid", "members", ["qq_unionid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_members_qq_unionid", table_name="members")
    op.drop_index("ix_members_qq_openid", table_name="members")
    op.drop_column("members", "qq_avatar_url")
    op.drop_column("members", "qq_nickname")
    op.drop_column("members", "qq_unionid")
    op.drop_column("members", "qq_openid")
