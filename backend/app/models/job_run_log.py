from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import now_naive


class JobRunLog(Base):
    __tablename__ = "job_run_logs"
    __table_args__ = (Index("ix_job_run_logs_run_id_id", "run_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_naive,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    logger: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_truncation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
