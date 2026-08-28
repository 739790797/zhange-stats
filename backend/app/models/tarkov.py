from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TarkovItemsRaw(Base):
    """逃离塔科夫物品上游原始响应（id=1 PVP，id=2 PVE）。"""

    __tablename__ = "tarkov_items_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    # GraphQL split 信封 / json.tarkov.dev items 信封，体积可能较大
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovItemsMeta(Base):
    """物品同步元数据（id=1 PVP，id=2 PVE；与 raw 同事务写入）。"""

    __tablename__ = "tarkov_items_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ammo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gun_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovAmmo(Base):
    """逃离塔科夫弹药（由 items raw 二次解析的派生读模型）。"""

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
    initial_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    accuracy_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    recoil_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    light_bleed_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    heavy_bleed_modifier: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    icon_link: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TarkovAmmoMeta(Base):
    """弹药展示元数据（单行 id=1；与 items 同步写入，供弹药 API）。"""

    __tablename__ = "tarkov_ammo_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ammo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovGun(Base):
    """逃离塔科夫枪械（由 items raw 二次解析的派生读模型）。"""

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
    """枪械展示元数据（单行 id=1；与 items 同步写入）。"""

    __tablename__ = "tarkov_gun_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gun_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovTasksRaw(Base):
    """逃离塔科夫任务上游原始响应（id=1 PVP，id=2 PVE）。"""

    __tablename__ = "tarkov_tasks_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovTasksMeta(Base):
    """任务同步元数据（id=1 PVP，id=2 PVE；与 raw 同事务写入）。"""

    __tablename__ = "tarkov_tasks_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovTradersRaw(Base):
    """逃离塔科夫商人上游原始响应（id=1 PVP，id=2 PVE）。"""

    __tablename__ = "tarkov_traders_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovTradersMeta(Base):
    """商人同步元数据（id=1 PVP，id=2 PVE；与 raw 同事务写入）。"""

    __tablename__ = "tarkov_traders_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trader_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    offer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovBossesRaw(Base):
    """逃离塔科夫 BOSS 上游原始响应（maps + mobs 精简包；id=1 PVP，id=2 PVE）。"""

    __tablename__ = "tarkov_bosses_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovBossesMeta(Base):
    """BOSS 同步元数据（id=1 PVP，id=2 PVE；与 raw 同事务写入）。"""

    __tablename__ = "tarkov_bosses_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    boss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovTrackerBind(Base):
    """当前用户的 Tarkov Tracker API token（Fernet 加密；API 不回传明文）。"""

    __tablename__ = "tarkov_tracker_binds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    token_suffix: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    game_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    player_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pmc_faction: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    game_edition: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_complete: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Tracker GET /progress 投影：player_level / pmc_faction / tasks{id→flags}
    progress_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TarkovGuidesRaw(Base):
    """藏身处 / 以物易物 / 制作上游原始响应（id=1 PVP，id=2 PVE）。"""

    __tablename__ = "tarkov_guides_raws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovGuidesMeta(Base):
    """藏身处 / 交换同步元数据（id=1 PVP，id=2 PVE）。"""

    __tablename__ = "tarkov_guides_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    station_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    barter_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    craft_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovRaidRoom(Base):
    """战局准备席位房：全站固定 1～5 号，空桌无房主；换图或清桌不留档。"""

    __tablename__ = "tarkov_raid_rooms"
    __table_args__ = (Index("ix_tarkov_raid_rooms_map_slug", "map_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    map_slug: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    host_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    host_display_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovRaidRoomMember(Base):
    """进过房间的人；离开删行。空桌无成员。"""

    __tablename__ = "tarkov_raid_room_members"

    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tarkov_raid_rooms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TarkovRaidRoomTaskClaim(Base):
    """房间任务勾选：同一任务多人署名（并集）。"""

    __tablename__ = "tarkov_raid_room_task_claims"

    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tarkov_raid_rooms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovRaidRoomKeyBring(Base):
    """房间钥匙声明：同一把钥匙可多人署名（备份），展示「谁带了」。"""

    __tablename__ = "tarkov_raid_room_key_brings"

    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tarkov_raid_rooms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovRaidRoomMark(Base):
    """房间画板：钉点 / 直线 / 自由笔画，坐标为地图 x/z。"""

    __tablename__ = "tarkov_raid_room_marks"
    __table_args__ = (Index("ix_tarkov_raid_room_marks_room", "room_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tarkov_raid_rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    floor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    x: Mapped[float] = mapped_column(Float, nullable=False)
    z: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    z2: Mapped[float | None] = mapped_column(Float, nullable=True)
    points_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
