"""Drop users.is_admin; CASCADE for Steam session FKs.

Revision ID: 20260805_0019
Revises: 20260805_0018
Create Date: 2026-08-05

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0019"
down_revision: Union[str, Sequence[str], None] = "20260805_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fks(table: str, column: str = "member_id") -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            name = fk.get("name")
            if name:
                op.drop_constraint(name, table, type_="foreignkey")


def upgrade() -> None:
    # role 为权限唯一来源：把旧 is_admin=1 回填到 role
    op.execute(
        sa.text(
            "UPDATE users SET role='admin' "
            "WHERE is_admin=1 AND (role IS NULL OR role<>'admin')"
        )
    )
    op.drop_column("users", "is_admin")

    _drop_fks("play_sessions")
    op.create_foreign_key(
        "fk_play_sessions_member_id_members",
        "play_sessions",
        "members",
        ["member_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _drop_fks("presence_segments")
    op.create_foreign_key(
        "fk_presence_segments_member_id_members",
        "presence_segments",
        "members",
        ["member_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.execute(sa.text("UPDATE users SET is_admin=1 WHERE role='admin'"))
    op.alter_column("users", "is_admin", server_default=None)

    _drop_fks("play_sessions")
    op.create_foreign_key(
        "fk_play_sessions_member_id_members",
        "play_sessions",
        "members",
        ["member_id"],
        ["id"],
    )

    _drop_fks("presence_segments")
    op.create_foreign_key(
        "fk_presence_segments_member_id_members",
        "presence_segments",
        "members",
        ["member_id"],
        ["id"],
    )
