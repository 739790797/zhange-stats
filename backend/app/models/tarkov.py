from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TarkovCatalogRawMixin:
    """图鉴 raw 同构列：一张上游文件一张表，locale 用 lang。"""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lang: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text(length=2**32 - 1), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TarkovItemsRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev items / items_zh。"""

    __tablename__ = "tarkov_items_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_items_raws_mode_lang"),
    )


class TarkovMapsRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev maps / maps_zh。"""

    __tablename__ = "tarkov_maps_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_maps_raws_mode_lang"),
    )


class TarkovTasksRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev tasks / tasks_zh。"""

    __tablename__ = "tarkov_tasks_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_tasks_raws_mode_lang"),
    )


class TarkovTradersRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev traders / traders_zh。"""

    __tablename__ = "tarkov_traders_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_traders_raws_mode_lang"),
    )


class TarkovHideoutRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev hideout / hideout_zh。"""

    __tablename__ = "tarkov_hideout_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_hideout_raws_mode_lang"),
    )


class TarkovBartersRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev barters。"""

    __tablename__ = "tarkov_barters_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_barters_raws_mode_lang"),
    )


class TarkovCraftsRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev crafts。"""

    __tablename__ = "tarkov_crafts_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_crafts_raws_mode_lang"),
    )


class TarkovExtrasRaw(TarkovCatalogRawMixin, Base):
    """json.tarkov.dev dump 抽出的 extras（成就 / 跳蚤规则 / 技能等）。"""

    __tablename__ = "tarkov_extras_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_extras_raws_mode_lang"),
    )


class TarkovOverlayRaw(TarkovCatalogRawMixin, Base):
    """tarkov-data-overlay dist/overlay.json。读库解析时与 json.tarkov.dev raw 内存合入。"""

    __tablename__ = "tarkov_overlay_raws"
    __table_args__ = (
        UniqueConstraint("mode_id", "lang", name="uq_tarkov_overlay_raws_mode_lang"),
    )


class TarkovAmmo(Base):
    """逃离塔科夫弹药（由 items raw 二次解析的派生读模型）。"""

    __tablename__ = "tarkov_ammo"

    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True)
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


class TarkovGun(Base):
    """逃离塔科夫枪械（由 items raw 二次解析的派生读模型）。"""

    __tablename__ = "tarkov_guns"

    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True)
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


class TarkovRaidRoom(Base):
    """联机大厅房间：登录用户创建；空房删除不留档。"""

    __tablename__ = "tarkov_raid_rooms"
    __table_args__ = (Index("ix_tarkov_raid_rooms_map_slug", "map_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    map_slug: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    game_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="pvp")
    listed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_task_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    task_progress_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


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


class TarkovUserTaskDone(Base):
    """用户任务完成：按 PVP/PVE 分开勾选，供个人中心任务树。"""

    __tablename__ = "tarkov_user_task_dones"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserTaskStarted(Base):
    """用户任务进行中：按 PVP/PVE 分开，与完成集合一起构成账号进度账。"""

    __tablename__ = "tarkov_user_task_starteds"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserTaskObjectiveDone(Base):
    """用户任务小步骤勾选：按 PVP/PVE 分开，与完成/进行中一起构成账号进度账。"""

    __tablename__ = "tarkov_user_task_objective_dones"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    objective_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserKeyOwn(Base):
    """用户仓库钥匙拥有：账号级，钥匙分类速查勾选，准备总结展示谁有。"""

    __tablename__ = "tarkov_user_key_owns"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserCollectionOwn(Base):
    """用户 3×4 收集勾选：按 PVP/PVE 分开，个人中心收集者道具清单。"""

    __tablename__ = "tarkov_user_collection_owns"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserCollectionLayout(Base):
    """用户 3×4 收集摆放过账号：空格子也算已保存，避免被本地旧数据盖回去。"""

    __tablename__ = "tarkov_user_collection_layouts"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserCollectionPlacement(Base):
    """用户 3×4 收集摆放：按 PVP/PVE 分开，格子坐标跟账号走。"""

    __tablename__ = "tarkov_user_collection_placements"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    col: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rotated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserRaidLog(Base):
    """用户从本机游戏日志导入的战局摘要（不含原文）。"""

    __tablename__ = "tarkov_user_raid_logs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "dedupe_key",
            name="uq_tarkov_user_raid_logs_user_dedupe",
        ),
        Index("ix_tarkov_user_raid_logs_user_started", "user_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    dedupe_key: Mapped[str] = mapped_column(String(220), nullable=False)
    folder: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    raid_id: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    map_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    map_label: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    raid_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    session_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    started_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    ended_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    reconnected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    aborted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TarkovUserRaidPrep(Base):
    """联机大厅单人准备：按账号 / 模式 / 地图保存勾选、目标完成和钥匙声明。"""

    __tablename__ = "tarkov_user_raid_preps"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_mode: Mapped[str] = mapped_column(String(8), primary_key=True)
    map_slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    selected_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    objective_dones_json: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    key_brings_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
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


class TarkovRaidRoomObjectiveDone(Base):
    """房间目标完成：同一目标可多人署名，准备总结列出已完成用户。"""

    __tablename__ = "tarkov_raid_room_objective_dones"

    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tarkov_raid_rooms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    objective_id: Mapped[str] = mapped_column(String(64), primary_key=True)
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


class TarkovMapPlace(Base):
    """管理员维护的全站地图地名（点 / 框），按互动图 normalizedName 共用。"""

    __tablename__ = "tarkov_map_places"
    __table_args__ = (
        Index("ix_tarkov_map_places_map_key", "map_key", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    map_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="point")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    z: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    z2: Mapped[float | None] = mapped_column(Float, nullable=True)
    label_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    label_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    floor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
