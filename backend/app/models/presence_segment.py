from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PresenceSegment(Base):
    """Steam 状态片段：离线 / 在线 / 游戏中。"""

    __tablename__ = "presence_segments"
    __table_args__ = (
        Index("ix_presence_segments_member_started", "member_id", "started_at"),
        Index("ix_presence_segments_member_ended", "member_id", "ended_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # offline | online | playing
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    steam_app_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    game_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="steam")

    member = relationship("Member", back_populates="presence_segments")
