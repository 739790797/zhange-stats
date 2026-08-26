"""Per-role auto checkin preferences (all platforms)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CheckinRolePref(Base):
    """按角色的「加入本站」与自动签到开关/时间（北京墙钟）。"""

    __tablename__ = "checkin_role_prefs"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "member_id",
            "game_code",
            "role_uid",
            name="uq_checkin_role_pref",
        ),
        Index(
            "ix_checkin_role_prefs_due",
            "platform",
            "enabled",
            "checkin_hour",
            "checkin_minute",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_code: Mapped[str] = mapped_column(String(32), nullable=False)
    role_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    # 是否加入本站（签到页展示 / 可手动签）；与 enabled 解耦
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checkin_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkin_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
