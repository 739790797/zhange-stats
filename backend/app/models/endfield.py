"""明日方舟：终末地 — 养成卡原始响应落库。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EndfieldBoxRaw(Base):
    """终末地 card/detail 原始 JSON（按角色保留最新一份）。"""

    __tablename__ = "endfield_box_raws"
    __table_args__ = (
        UniqueConstraint("member_id", "role_id", name="uq_endfield_box_raw_member_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(String(64), nullable=False)
    server_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uid: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # 上游整包响应，体积可能较大
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EndfieldAttendanceRaw(Base):
    """终末地签到 GET attendance 原始 JSON（按 member+role 最新一份，跨月可读）。"""

    __tablename__ = "endfield_attendance_raws"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "role_id",
            name="uq_endfield_attendance_raw_member_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(String(64), nullable=False)
    server_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uid: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    role_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
