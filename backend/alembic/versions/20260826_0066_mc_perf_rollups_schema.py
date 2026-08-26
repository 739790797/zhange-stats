"""Minecraft perf rollups, bind last_checkin drop, indexes, members CASCADE.

Revision ID: 20260826_0066
Revises: 20260825_0065
Create Date: 2026-08-26

MySQL/MariaDB DDL is non-transactional, so upgrade must be idempotent.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0066"
down_revision: Union[str, Sequence[str], None] = "20260825_0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIND_TABLES = (
    "skland_binds",
    "taygedo_binds",
    "exilium_binds",
    "kujiequ_binds",
    "mihoyo_binds",
)
_LAST_CHECKIN_COLS = (
    "last_checkin_at",
    "last_checkin_date",
    "last_checkin_summary",
    "last_checkin_ok",
)
_DROP_INDEXES = (
    ("play_sessions", "ix_play_sessions_member_id"),
    ("presence_segments", "ix_presence_segments_member_id"),
    ("skland_checkin_logs", "ix_skland_checkin_logs_member_id"),
    ("taygedo_checkin_logs", "ix_taygedo_checkin_logs_member_id"),
    ("exilium_checkin_logs", "ix_exilium_checkin_logs_member_id"),
    ("kujiequ_checkin_logs", "ix_kujiequ_checkin_logs_member_id"),
    ("mihoyo_checkin_logs", "ix_mihoyo_checkin_logs_member_id"),
    ("checkin_role_prefs", "ix_checkin_role_prefs_platform"),
    ("minecraft_presence_segments", "ix_minecraft_presence_segments_player_key"),
    ("minecraft_presence_segments", "ix_minecraft_presence_segments_status"),
    ("job_runs", "ix_job_runs_job_key"),
)
_ADD_INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("ix_checkin_role_prefs_due", "checkin_role_prefs", [
        "platform", "enabled", "checkin_hour", "checkin_minute",
    ]),
    ("ix_job_runs_job_key_started", "job_runs", ["job_key", "started_at"]),
    ("ix_oauth_exchange_tickets_expires_at", "oauth_exchange_tickets", ["expires_at"]),
    ("ix_register_challenges_expires_at", "register_challenges", ["expires_at"]),
)


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table) if ix.get("name")}


def _drop_index(table: str, name: str) -> None:
    if name in _index_names(table):
        op.drop_index(name, table_name=table)


def _create_index(name: str, table: str, cols: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    if name in _index_names(table):
        return
    op.create_index(name, table, cols, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "minecraft_perf_rollups" not in tables:
        op.create_table(
            "minecraft_perf_rollups",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("grain", sa.String(length=8), nullable=False),
            sa.Column("bucket_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tps_avg", sa.Float(), nullable=True),
            sa.Column("tps_min", sa.Float(), nullable=True),
            sa.Column("tps_max", sa.Float(), nullable=True),
            sa.Column("mspt_avg", sa.Float(), nullable=True),
            sa.Column("mspt_min", sa.Float(), nullable=True),
            sa.Column("mspt_max", sa.Float(), nullable=True),
            sa.Column("entities_avg", sa.Float(), nullable=True),
            sa.Column("entities_max", sa.Float(), nullable=True),
            sa.Column("chunks_avg", sa.Float(), nullable=True),
            sa.Column("chunks_max", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "grain", "bucket_at", name="uq_mc_perf_rollup_grain_bucket"
            ),
        )
        op.create_index(
            "ix_minecraft_perf_rollups_bucket_at",
            "minecraft_perf_rollups",
            ["bucket_at"],
            unique=False,
        )

    for table in _BIND_TABLES:
        if table not in tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        for col in _LAST_CHECKIN_COLS:
            if col in cols:
                op.drop_column(table, col)

    if "members" in tables:
        fresh = sa.inspect(bind)
        has_cascade = False
        for fk in fresh.get_foreign_keys("members"):
            if "user_id" not in (fk.get("constrained_columns") or []):
                continue
            ondelete = str((fk.get("options") or {}).get("ondelete") or "").upper()
            name = fk.get("name")
            if ondelete == "CASCADE":
                has_cascade = True
                continue
            if name:
                op.drop_constraint(name, "members", type_="foreignkey")
        if not has_cascade:
            op.create_foreign_key(
                "fk_members_user_id_users",
                "members",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    for table, name in _DROP_INDEXES:
        _drop_index(table, name)
    for name, table, cols in _ADD_INDEXES:
        _create_index(name, table, cols)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for name, table, _cols in reversed(_ADD_INDEXES):
        _drop_index(table, name)
    for table, name in reversed(_DROP_INDEXES):
        if table not in tables:
            continue
        if name == "ix_job_runs_job_key":
            _create_index(name, table, ["job_key"])
        elif name.endswith("_member_id"):
            _create_index(name, table, ["member_id"])
        elif name == "ix_checkin_role_prefs_platform":
            _create_index(name, table, ["platform"])
        elif name == "ix_minecraft_presence_segments_player_key":
            _create_index(name, table, ["player_key"])
        elif name == "ix_minecraft_presence_segments_status":
            _create_index(name, table, ["status"])

    if "members" in tables:
        for fk in sa.inspect(bind).get_foreign_keys("members"):
            if "user_id" in (fk.get("constrained_columns") or []):
                name = fk.get("name")
                if name:
                    op.drop_constraint(name, "members", type_="foreignkey")
        op.create_foreign_key(
            "fk_members_user_id_users",
            "members",
            "users",
            ["user_id"],
            ["id"],
        )

    for table in _BIND_TABLES:
        if table not in tables:
            continue
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if "last_checkin_at" not in cols:
            op.add_column(
                table,
                sa.Column("last_checkin_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "last_checkin_date" not in cols:
            op.add_column(table, sa.Column("last_checkin_date", sa.Date(), nullable=True))
        if "last_checkin_summary" not in cols:
            op.add_column(table, sa.Column("last_checkin_summary", sa.Text(), nullable=True))
        if "last_checkin_ok" not in cols:
            op.add_column(table, sa.Column("last_checkin_ok", sa.Boolean(), nullable=True))

    if "minecraft_perf_rollups" in tables:
        _drop_index("minecraft_perf_rollups", "ix_minecraft_perf_rollups_bucket_at")
        op.drop_table("minecraft_perf_rollups")
