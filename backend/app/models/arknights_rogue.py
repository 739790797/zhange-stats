"""明日方舟集成战略（肉鸽）原始响应落库。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ArknightsRogueRaw(Base):
    """方舟肉鸽 GET /game/arknights/rogue 原始 JSON（按 uid+主题 最新一份）。"""

    __tablename__ = "arknights_rogue_raws"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "uid",
            "topic_id",
            name="uq_arknights_rogue_raw_member_uid_topic",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
