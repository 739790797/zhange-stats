"""新图鉴游戏的上游原文。一个外部文件一行。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.sqltypes import LongText
from app.core.timeutil import now_naive


class GuideRaw(Base):
    """``game`` + ``resource`` 唯一。正文可以是 gz1:。"""

    __tablename__ = "guide_raws"
    __table_args__ = (UniqueConstraint("game", "resource", name="uq_guide_raws_game_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game: Mapped[str] = mapped_column(String(32), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_body: Mapped[str] = mapped_column(LongText, nullable=False, deferred=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=now_naive,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
