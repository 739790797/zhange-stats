from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RumSample(Base):
    """浏览器 RUM 原始样本（接口等待 / 第三方图）。保留约 14 天。"""

    __tablename__ = "rum_samples"
    __table_args__ = (Index("ix_rum_samples_kind_recorded", "kind", "recorded_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    url_key: Mapped[str] = mapped_column(String(256), nullable=False)
    host: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    page_path: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)
