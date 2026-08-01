from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SteamFriendEdge(Base):
    """某成员 Steam 好友列表中的一条边（同步自 GetFriendList）。"""

    __tablename__ = "steam_friend_edges"
    __table_args__ = (
        UniqueConstraint("member_id", "friend_steam_id", name="uq_steam_friend_edge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    friend_steam_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    friend_since: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    member = relationship("Member", back_populates="steam_friend_edges")
