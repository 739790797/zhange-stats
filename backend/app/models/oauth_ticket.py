from datetime import datetime

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import now_naive


class OAuthExchangeTicket(Base):
    """QQ 等 OAuth 回调用的一次性换票码（避免 JWT 进 URL）。"""

    __tablename__ = "oauth_exchange_tickets"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet enc:v1:…
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_naive,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
