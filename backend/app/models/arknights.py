from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ArknightsOperator(Base):
    """明日方舟干员图鉴（自 ArknightsGameResource character_table 同步）。"""

    __tablename__ = "arknights_operators"

    char_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rarity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    profession: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    profession_label: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    sort_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ArknightsCatalogMeta(Base):
    """图鉴同步元数据（单行 id=1）。"""

    __tablename__ = "arknights_catalog_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ArknightsBoxSnapshot(Base):
    """明日方舟盒子练度快照（按角色 uid 日更缓存）。"""

    __tablename__ = "arknights_box_snapshots"
    __table_args__ = (
        UniqueConstraint("member_id", "uid", name="uq_arknights_box_snapshot_member_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    # 满练度盒子含技能/模组，JSON 常超 TEXT(64KB)，需 LONGTEXT
    payload_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    sync_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
