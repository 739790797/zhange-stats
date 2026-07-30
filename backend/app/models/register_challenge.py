from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RegisterChallenge(Base):
    """注册前邮箱验证码挑战。"""

    __tablename__ = "register_challenges"

    email: Mapped[str] = mapped_column(String(128), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
