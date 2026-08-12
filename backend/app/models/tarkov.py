from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TarkovAmmoRaw(Base):
    """逃离塔科夫弹药上游原始响应（全站最新一份成功同步）。"""

    __tablename__ = "tarkov_ammo_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    # GraphQL / json.tarkov.dev envelope / tarkovdata 整包，体积可能较大
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovAmmo(Base):
    """逃离塔科夫弹药（由 raw 二次解析的派生读模型）。"""

    __tablename__ = "tarkov_ammo"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    caliber: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 上游 properties.ammoType：bullet / buckshot / grenade / flashbang 等
    ammo_type: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
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
    """弹药同步元数据（单行 id=1；与 raw 同步写入，供 API 展示）。"""

    __tablename__ = "tarkov_ammo_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ammo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovGunRaw(Base):
    """逃离塔科夫枪械上游原始响应（全站最新一份成功同步）。"""

    __tablename__ = "tarkov_gun_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovGun(Base):
    """逃离塔科夫枪械（由 raw 二次解析的派生读模型）。"""

    __tablename__ = "tarkov_guns"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    caliber: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    weapon_class: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    fire_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ergonomics: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    recoil_vertical: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recoil_horizontal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_distance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fire_modes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    default_ammo_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    allowed_ammo_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    icon_link: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TarkovGunMeta(Base):
    """枪械同步元数据（单行 id=1）。"""

    __tablename__ = "tarkov_gun_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gun_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
