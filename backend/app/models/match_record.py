import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MatchResult(str, enum.Enum):
    win = "win"
    lose = "lose"
    draw = "draw"
    unknown = "unknown"


class MatchSource(str, enum.Enum):
    manual = "manual"
    import_ = "import"
    crawler = "crawler"


class MatchRecord(Base):
    __tablename__ = "match_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    result: Mapped[MatchResult] = mapped_column(
        Enum(MatchResult, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MatchResult.unknown,
    )
    mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[MatchSource] = mapped_column(
        Enum(MatchSource, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MatchSource.manual,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    member = relationship("Member", back_populates="records")
    game = relationship("Game", back_populates="records")
