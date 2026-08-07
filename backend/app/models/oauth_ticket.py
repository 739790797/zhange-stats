from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OAuthExchangeTicket(Base):
    """QQ 等 OAuth 回调用的一次性换票码（避免 JWT 进 URL）。"""

    __tablename__ = "oauth_exchange_tickets"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet enc:v1:…
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
