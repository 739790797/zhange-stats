from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlaySession(Base):
    __tablename__ = "play_sessions"
    __table_args__ = (
        Index("ix_play_sessions_member_started", "member_id", "started_at"),
        Index("ix_play_sessions_member_ended", "member_id", "ended_at"),
        Index("ix_play_sessions_source_started", "source", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    steam_app_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    game_name: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="steam")

    member = relationship("Member", back_populates="play_sessions")
