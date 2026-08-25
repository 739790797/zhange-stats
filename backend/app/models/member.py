from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
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
    steam_persona_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    steam_avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qq_openid: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    qq_unionid: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    qq_nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qq_avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="member")
    play_sessions = relationship(
        "PlaySession", back_populates="member", passive_deletes=True
    )
    presence_segments = relationship(
        "PresenceSegment", back_populates="member", passive_deletes=True
    )
    skland_bind = relationship(
        "SklandBind",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )
    taygedo_bind = relationship(
        "TaygedoBind",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )
    exilium_bind = relationship(
        "ExiliumBind",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )
    kujiequ_bind = relationship(
        "KujiequBind",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mihoyo_bind = relationship(
        "MihoyoBind",
        back_populates="member",
        uselist=False,
        cascade="all, delete-orphan",
    )
