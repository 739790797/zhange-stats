from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Cs2Match(Base):
    __tablename__ = "cs2_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    outcome_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    token: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    map_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    score_team0: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_team1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    enriched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    players = relationship("Cs2MatchPlayer", back_populates="match", cascade="all, delete-orphan")


class Cs2MatchPlayer(Base):
    __tablename__ = "cs2_match_players"
    __table_args__ = (
        UniqueConstraint("match_id", "steam_id", name="uq_cs2_match_player"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("cs2_matches.match_id"), nullable=False, index=True
    )
    steam_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id"), nullable=True, index=True
    )
    team: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mvps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    damage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    persona_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    match = relationship("Cs2Match", back_populates="players")
    member = relationship("Member")
