from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SteamApp(Base):
    """Steam AppID → 商店展示信息缓存（简体名 / 头图 / 价格）。"""

    __tablename__ = "steam_apps"

    app_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    header_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    capsule_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    initial_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initial_formatted: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_formatted: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    details_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
