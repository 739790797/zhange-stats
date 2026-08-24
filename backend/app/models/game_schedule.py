from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GameScheduleRaw(Base):
    """game-schedule 活动日历上游原始 JSON（按游戏一份；失败不覆盖）。"""

    __tablename__ = "game_schedule_raws"

    game: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="game-schedule")
    upstream_base: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
