from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MihoyoBind(Base):
    """米游社账号绑定（Cookie / Stoken 加密存储）。"""

    __tablename__ = "mihoyo_binds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    credentials_enc: Mapped[str] = mapped_column(Text, nullable=False)
    phone_mask: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auto_checkin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checkin_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkin_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_checkin_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_checkin_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checkin_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    member = relationship("Member", back_populates="mihoyo_bind")
    logs = relationship(
        "MihoyoCheckinLog",
        back_populates="bind",
        cascade="all, delete-orphan",
    )


class MihoyoCheckinLog(Base):
    """米游社签到 / 状态查询记录。"""

    __tablename__ = "mihoyo_checkin_logs"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "checkin_date",
            "game_code",
            "role_uid",
            name="uq_mihoyo_checkin_day_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bind_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mihoyo_binds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_code: Mapped[str] = mapped_column(String(32), nullable=False)
    game_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    role_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    awards_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    awards_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="status")
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bind = relationship("MihoyoBind", back_populates="logs")
    member = relationship("Member")


class MihoyoAttendanceRaw(Base):
    """米游社游戏福利签到日历原始 JSON（info + home，按角色最新一份）。"""

    __tablename__ = "mihoyo_attendance_raws"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "game_code",
            "role_uid",
            name="uq_mihoyo_attendance_raw_member_game_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_code: Mapped[str] = mapped_column(String(32), nullable=False)
    role_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    role_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    game_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
