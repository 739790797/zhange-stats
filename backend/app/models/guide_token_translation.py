"""Parsed translation cache for source tokens served by Weblate."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.sqltypes import LongText
from app.core.timeutil import now_naive


class GuideTokenTranslation(Base):
    """One cached Weblate unit, keyed by a digest of its context."""

    __tablename__ = "guide_token_translations"
    __table_args__ = (
        UniqueConstraint(
            "game",
            "target_language",
            "context_hash",
            name="uq_guide_token_translations_context",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game: Mapped[str] = mapped_column(String(32), nullable=False)
    target_language: Mapped[str] = mapped_column(String(32), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(LongText, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    target_text: Mapped[str | None] = mapped_column(LongText, nullable=True)
    translation_state: Mapped[str] = mapped_column(String(24), nullable=False)


class GuideTokenTranslationSync(Base):
    """Successful Weblate snapshot marker, including an intentionally empty snapshot."""

    __tablename__ = "guide_token_translation_syncs"

    game: Mapped[str] = mapped_column(String(32), primary_key=True)
    target_language: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_naive
    )