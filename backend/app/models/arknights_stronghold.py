"""卫戍协议场次、成员角色与角色战报。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import now_naive


class StrongholdRole(Base):
    __tablename__ = "arknights_stronghold_roles"
    __table_args__ = (
        UniqueConstraint("member_id", "channel_id", "uid", name="uq_sh_role_member_identity"),
        Index("ix_sh_role_identity", "channel_id", "uid"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    channel_id: Mapped[str] = mapped_column(String(8))
    uid: Mapped[str] = mapped_column(String(32))
    role_name: Mapped[str] = mapped_column(String(96))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StrongholdMatch(Base):
    __tablename__ = "arknights_stronghold_matches"
    __table_args__ = (
        Index("ix_sh_match_scope_ended", "season_id", "difficulty_id", "ended_at"),
        Index("ix_sh_match_ended", "ended_at", "id"),
        Index("ix_sh_match_version_ended", "season_id", "version_id", "ended_at"),
        Index("uq_sh_match_scene_key", "scene_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    # Retain the historical column for downgrade compatibility.
    identity_kind: Mapped[str] = mapped_column(String(16), server_default=text("'verified'"))
    # New rows hash the activity and case-sensitive scene ID into a portable unique key.
    scene_key: Mapped[str | None] = mapped_column(String(64))
    version_id: Mapped[str | None] = mapped_column(String(128))
    season_id: Mapped[str] = mapped_column(String(64))
    season_label: Mapped[str] = mapped_column(String(96))
    difficulty_id: Mapped[str] = mapped_column(String(64))
    difficulty_label: Mapped[str] = mapped_column(String(96))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mode_type: Mapped[str | None] = mapped_column(String(16))
    # Pre-existing whole-match result; not a source of personal wins.
    success: Mapped[bool] = mapped_column(Boolean)


class StrongholdMatchAlias(Base):
    __tablename__ = "arknights_stronghold_match_aliases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("arknights_stronghold_matches.id", ondelete="CASCADE"), index=True)


class StrongholdParticipant(Base):
    __tablename__ = "arknights_stronghold_participants"
    __table_args__ = (Index("ix_sh_participant_identity", "channel_id", "uid"),)

    match_id: Mapped[str] = mapped_column(
        ForeignKey("arknights_stronghold_matches.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    uid: Mapped[str] = mapped_column(String(32), primary_key=True)


class StrongholdRecord(Base):
    __tablename__ = "arknights_stronghold_records"
    __table_args__ = (
        UniqueConstraint("role_id", "season_id", "source_view_key", name="uq_sh_record_role_source"),
        UniqueConstraint("match_id", "role_id", name="uq_sh_record_match_role"),
        Index("ix_sh_record_role_ended", "role_id", "ended_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("arknights_stronghold_roles.id", ondelete="CASCADE"))
    match_id: Mapped[str] = mapped_column(ForeignKey("arknights_stronghold_matches.id", ondelete="CASCADE"))
    source_view_key: Mapped[str | None] = mapped_column(String(64))
    snapshot_key: Mapped[str | None] = mapped_column(String(64))
    version_id: Mapped[str | None] = mapped_column(String(128))
    season_id: Mapped[str] = mapped_column(String(64))
    season_label: Mapped[str] = mapped_column(String(96))
    difficulty_id: Mapped[str] = mapped_column(String(64))
    difficulty_label: Mapped[str] = mapped_column(String(96))
    mode_type: Mapped[str | None] = mapped_column(String(16))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    complete_state: Mapped[bool | None] = mapped_column(Boolean)
    pass_round: Mapped[int | None]
    strategy_id: Mapped[str | None] = mapped_column(String(128))
    strategy_name: Mapped[str | None] = mapped_column(String(96))
    roster: Mapped[list[dict] | None] = mapped_column(JSON(none_as_null=True))
    details: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    # Distinguishes a known empty list from an absent source field.
    bonds_known: Mapped[bool] = mapped_column(Boolean, server_default=text("0"))


class StrongholdRecordBond(Base):
    __tablename__ = "arknights_stronghold_view_bonds"

    view_id: Mapped[str] = mapped_column(
        ForeignKey("arknights_stronghold_records.id", ondelete="CASCADE"), primary_key=True
    )
    bond_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(96))
    icon_url: Mapped[str | None] = mapped_column(String(512))
    active: Mapped[bool | None] = mapped_column(Boolean)
    layer: Mapped[int | None]
    layer_scope: Mapped[str | None] = mapped_column(String(16))


class StrongholdRecordAlias(Base):
    __tablename__ = "arknights_stronghold_record_aliases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("arknights_stronghold_records.id", ondelete="CASCADE"), index=True
    )


class StrongholdVersion(Base):
    __tablename__ = "arknights_stronghold_versions"

    season_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(96))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Only projected display resources. Never stores credentials or personal history.
    catalog: Mapped[dict] = mapped_column(JSON, default=dict)
    assets: Mapped[dict] = mapped_column(JSON, default=dict)


class StrongholdActivity(Base):
    __tablename__ = "arknights_stronghold_activities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resource_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_naive)
    last_resource_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StrongholdSyncTarget(Base):
    __tablename__ = "arknights_stronghold_sync_targets"
    __table_args__ = (Index("ix_sh_sync_due", "due_at"),)

    bind_id: Mapped[int] = mapped_column(ForeignKey("skland_binds.id", ondelete="CASCADE"), primary_key=True)
    # The empty channel/UID pair is the binding's role discovery task.
    channel_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    uid: Mapped[str] = mapped_column(String(32), primary_key=True)
    binding_key: Mapped[str] = mapped_column(String(64))
    role_name: Mapped[str] = mapped_column(String(96), default="")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_naive)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_battle_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested: Mapped[bool] = mapped_column(Boolean, default=False)
    failures: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="queued")


class StrongholdSyncControl(Base):
    __tablename__ = "arknights_stronghold_sync_control"

    id: Mapped[int] = mapped_column(primary_key=True)
    retry_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovery_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
