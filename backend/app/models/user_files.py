"""用户附件登记（user_files）：流水号 + 相对路径，与管理端 file_manager 分开。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserFile(Base):
    __tablename__ = "user_files"
    __table_args__ = (
        UniqueConstraint("serial", name="uq_user_files_serial"),
        UniqueConstraint("rel_path", name="uq_user_files_rel_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial: Mapped[str] = mapped_column(String(32), nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rel_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="public")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="stored")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
