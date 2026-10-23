"""Cache parsed Weblate token units separately from upstream Wiki raws.

Revision ID: 20261022_0128
Revises: 20261020_0127
Create Date: 2026-10-22

MariaDB note: DDL is non-transactional; CREATE gated on inspect.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "20261022_0128"
down_revision: Union[str, Sequence[str], None] = "20261020_0127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRANSLATIONS = "guide_token_translations"
_SYNC_STATES = "guide_token_translation_syncs"
_CONTEXT_UNIQUE = "uq_guide_token_translations_context"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TRANSLATIONS not in tables:
        op.create_table(
            _TRANSLATIONS,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("game", sa.String(length=32), nullable=False),
            sa.Column("target_language", sa.String(length=32), nullable=False),
            sa.Column("context_hash", sa.String(length=64), nullable=False),
            sa.Column("context", sa.Text(), nullable=False),
            sa.Column("source_text", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=False),
            sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("target_text", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
            sa.Column("translation_state", sa.String(length=24), nullable=False),
            sa.UniqueConstraint(
                "game",
                "target_language",
                "context_hash",
                name=_CONTEXT_UNIQUE,
            ),
        )
    if _SYNC_STATES not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            _SYNC_STATES,
            sa.Column("game", sa.String(length=32), primary_key=True, nullable=False),
            sa.Column("target_language", sa.String(length=32), primary_key=True, nullable=False),
            sa.Column("scope_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("source_manifest_fingerprint", sa.String(length=64), nullable=True),
            sa.Column("snapshot_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("unit_count", sa.Integer(), nullable=False),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _SYNC_STATES in tables:
        op.drop_table(_SYNC_STATES)
    if _TRANSLATIONS in tables:
        op.drop_table(_TRANSLATIONS)