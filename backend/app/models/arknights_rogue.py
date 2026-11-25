"""退役的明日方舟集成战略缓存。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.sqltypes import LongText
from app.core.timeutil import now_naive


class ArknightsRogueRaw(Base):
    """保留既有数据供签到与干员对比读取历史角色 UID。"""

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
    raw_json: Mapped[str] = mapped_column(LongText, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=now_naive,
        server_default=text("CURRENT_TIMESTAMP"),
    )
