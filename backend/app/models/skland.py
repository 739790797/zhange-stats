from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SklandBind(Base):
    """森空岛凭证绑定（鹰角通行证 token，加密存储）。"""

    __tablename__ = "skland_binds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    auto_checkin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checkin_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkin_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # 反规范化摘要：调度跳过 / 管理端任务列表；今日按角色详情以 logs 为准
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

    member = relationship("Member", back_populates="skland_bind")
    logs = relationship(
        "SklandCheckinLog",
        back_populates="bind",
        cascade="all, delete-orphan",
    )


class SklandCheckinLog(Base):
    """森空岛签到 / 状态查询记录（按「今日」缓存读优先，见 platform-raw-cache）。"""

    __tablename__ = "skland_checkin_logs"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "checkin_date",
            "game_code",
            "role_uid",
            name="uq_skland_checkin_day_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bind_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skland_binds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_code: Mapped[str] = mapped_column(String(32), nullable=False)
    game_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    role_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    awards_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 结构化奖励 JSON：[{name,count,resource_type,icon_url?}, ...]
    awards_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status=查询/同步缓存；action=真正执行签到（执行记录只看 action）
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="status")
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bind = relationship("SklandBind", back_populates="logs")
    member = relationship("Member")


class SklandAttendanceRaw(Base):
    """明日方舟签到 GET attendance 原始 JSON（按 uid 最新一份，跨日可读）。"""

    __tablename__ = "skland_attendance_raws"
    __table_args__ = (
        UniqueConstraint(
            "member_id", "uid", name="uq_skland_attendance_raw_member_uid"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
