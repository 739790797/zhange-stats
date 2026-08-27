from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PROFILE_ROW_ID = 1


class MinecraftServerProfile(Base):
    """圈子 Minecraft 单行档案（永远一行 id=1）。

    `applied_json` 是上次成功应用时的快照，总览用它回填模组标题/版本。
    `mod_presets_json` 是模组键值预设（按 tool_id 存 directories 为用户选定的配置目录，
    以及 pins：file 为服内绝对路径、须落在这些目录内，加上 key/value）；
    对账后写入服上走 Pelican。
    `mod_inventory_json` 是当前服 /mods 与 /plugins 的 jar 库存（权威在战鸽；
    Pelican 只当网盘。打开页对账指纹，增量拆包认亲）。
    """

    __tablename__ = "minecraft_server_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mc_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.21.1")
    loader: Mapped[str] = mapped_column(String(32), nullable=False, default="fabric")
    loader_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    egg_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    startup: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mods_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    overrides_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    applied_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    mod_presets_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    mod_inventory_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    last_applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_apply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MinecraftPerfSample(Base):
    """RCON 性能采样（约 10 秒一次；只保留最近约 48 小时）。

    更长窗口读 `minecraft_perf_rollups`。`entities` / `chunks` 为可选旁路指标
    （实体来自 entity list 缓存；区块来自 Essentials `gc` 等尽力解析）。
    """

    __tablename__ = "minecraft_perf_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    tps: Mapped[float | None] = mapped_column(Float, nullable=True)
    mspt: Mapped[float | None] = mapped_column(Float, nullable=True)
    entities: Mapped[float | None] = mapped_column(Float, nullable=True)
    chunks: Mapped[float | None] = mapped_column(Float, nullable=True)


class MinecraftPerfRollup(Base):
    """性能采样聚合档：1 分钟 / 1 小时 / 1 天各一份桶。

    30m/1h 读原始 10 秒点；12h/24h 读 1m；30d 读 1h；all 读 1d。
    1m 保留约 30 天，1h/1d 永久。
    """

    __tablename__ = "minecraft_perf_rollups"
    __table_args__ = (
        UniqueConstraint("grain", "bucket_at", name="uq_mc_perf_rollup_grain_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grain: Mapped[str] = mapped_column(String(8), nullable=False)
    bucket_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tps_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    tps_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    tps_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    mspt_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    mspt_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    mspt_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    entities_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    entities_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    chunks_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    chunks_max: Mapped[float | None] = mapped_column(Float, nullable=True)


class MinecraftPresenceSegment(Base):
    """Minecraft 玩家在线/离线片段（总览时间轴）。"""

    __tablename__ = "minecraft_presence_segments"
    __table_args__ = (
        Index("ix_mc_presence_player_started", "player_key", "started_at"),
        Index("ix_mc_presence_player_ended", "player_key", "ended_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_key: Mapped[str] = mapped_column(String(80), nullable=False)
    player_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    player_uuid: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    # online | offline
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
