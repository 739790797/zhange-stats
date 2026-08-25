from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PROFILE_ROW_ID = 1


class MinecraftServerProfile(Base):
    """圈子 Minecraft 开服剧本草稿（永远一行 id=1）。

    行内字段只描述下次要应用的剧本（版本 / 加载器 / Egg / 启动命令 / 模组 / 配置），
    不镜像当前 Pelican 服的实时状态。`applied_json` 是上次成功应用时的快照。
    `mod_presets_json` 是模组草稿预设（按 tool_id / preset_id 存正文），
    出厂模板仍在代码里；写入服上走 Pelican。
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
    """RCON 性能采样（约 10 秒一次；总览按时间窗分桶展示）。

    `entities` / `chunks` 为可选旁路指标（实体来自 entity list 缓存；
    区块来自 Essentials `gc` 等尽力解析，拿不到则为空）。
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


class MinecraftPresenceSegment(Base):
    """Minecraft 玩家在线/离线片段（总览时间轴）。"""

    __tablename__ = "minecraft_presence_segments"
    __table_args__ = (
        Index("ix_mc_presence_player_started", "player_key", "started_at"),
        Index("ix_mc_presence_player_ended", "player_key", "ended_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    player_uuid: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    # online | offline
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
