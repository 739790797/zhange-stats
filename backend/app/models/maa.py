"""MAA 全托管槽位台账、审计与日常任务。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
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

# provisioning | online | offline | destroying | destroyed | error
MAA_SLOT_STATUSES = frozenset(
    {"provisioning", "online", "offline", "destroying", "destroyed", "error"}
)
# provision | start | stop | destroy | None
MAA_DESIRED_ACTIONS = frozenset({"provision", "start", "stop", "destroy"})
# daily | stop
MAA_JOB_TYPES = frozenset({"daily", "stop"})
# queued | running | success | failed | cancelled
MAA_JOB_STATUSES = frozenset(
    {"queued", "running", "success", "failed", "cancelled"}
)


class MaaSlot(Base):
    __tablename__ = "maa_slots"
    __table_args__ = (
        UniqueConstraint("bound_member_id", name="uq_maa_slots_bound_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    desired_action: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    volume_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    adb_endpoint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bound_member_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # 规格（预留；MVP 用默认值）
    cpu_limit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    memory_limit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False, default="720x1280")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_screenshot_relpath: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_screenshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cpu_percent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    memory_usage_mb: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    destroyed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    bound_member = relationship("Member", foreign_keys=[bound_member_id])
    audits = relationship(
        "MaaSlotAudit",
        back_populates="slot",
        cascade="all, delete-orphan",
        order_by="MaaSlotAudit.id.desc()",
    )
    jobs = relationship(
        "MaaJob",
        back_populates="slot",
        cascade="all, delete-orphan",
    )


class MaaSlotAudit(Base):
    __tablename__ = "maa_slot_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maa_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    admin_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    slot = relationship("MaaSlot", back_populates="audits")


class MaaJob(Base):
    __tablename__ = "maa_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maa_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    slot = relationship("MaaSlot", back_populates="jobs")
