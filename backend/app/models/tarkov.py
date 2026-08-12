from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TarkovAmmo(Base):
    """逃离塔科夫弹药（自 tarkov.dev / 社区数据同步）。"""

    __tablename__ = "tarkov_ammo"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    caliber: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    damage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    penetration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    armor_damage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TarkovAmmoMeta(Base):
    """弹药同步元数据（单行 id=1）。"""

    __tablename__ = "tarkov_ammo_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ammo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
