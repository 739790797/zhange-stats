from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    steam_id: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True, index=True
    )
    steam_friends_public: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    steam_friends_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="member")
    play_sessions = relationship("PlaySession", back_populates="member")
    presence_segments = relationship("PresenceSegment", back_populates="member")
    steam_friend_edges = relationship(
        "SteamFriendEdge", back_populates="member", cascade="all, delete-orphan"
    )
