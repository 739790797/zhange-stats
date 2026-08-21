"""register_challenges: composite PK (email, purpose).

Revision ID: 20260821_0058
Revises: 20260821_0057
Create Date: 2026-08-21

Ephemeral verification codes; drop/recreate is safe.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0058"
down_revision: Union[str, Sequence[str], None] = "20260821_0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("register_challenges")}
    pk = sa.inspect(bind).get_pk_constraint("register_challenges") or {}
    pk_cols = list(pk.get("constrained_columns") or [])
    if "purpose" in cols and pk_cols == ["email", "purpose"]:
        return

    op.drop_table("register_challenges")
    op.create_table(
        "register_challenges",
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email", "purpose"),
    )


def downgrade() -> None:
    op.drop_table("register_challenges")
    op.create_table(
        "register_challenges",
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )
