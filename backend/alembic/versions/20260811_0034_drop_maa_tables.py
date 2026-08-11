"""Drop MAA tables (feature removed).

Revision ID: 20260811_0034
Revises: 20260810_0033
Create Date: 2026-08-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0034"
down_revision: Union[str, Sequence[str], None] = "20260810_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("maa_jobs")
    op.drop_table("maa_slot_audits")
    op.drop_table("maa_slots")
    op.execute(sa.text("DELETE FROM system_configs WHERE `key` = 'maa_host_stats'"))


def downgrade() -> None:
    # Mirror 20260810_0033 upgrade (feature no longer maintained).
    op.create_table(
        "maa_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("desired_action", sa.String(length=32), nullable=True),
        sa.Column("container_name", sa.String(length=128), nullable=True),
        sa.Column("volume_name", sa.String(length=128), nullable=True),
        sa.Column("adb_endpoint", sa.String(length=128), nullable=True),
        sa.Column("bound_member_id", sa.Integer(), nullable=True),
        sa.Column("cpu_limit", sa.String(length=32), nullable=True),
        sa.Column("memory_limit", sa.String(length=32), nullable=True),
        sa.Column("resolution", sa.String(length=32), nullable=False, server_default="720x1280"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_screenshot_relpath", sa.String(length=512), nullable=True),
        sa.Column("last_screenshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cpu_percent", sa.String(length=32), nullable=True),
        sa.Column("memory_usage_mb", sa.String(length=32), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bound_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bound_member_id", name="uq_maa_slots_bound_member"),
    )
    op.create_index(op.f("ix_maa_slots_status"), "maa_slots", ["status"], unique=False)
    op.create_index(
        op.f("ix_maa_slots_desired_action"), "maa_slots", ["desired_action"], unique=False
    )
    op.create_index(
        op.f("ix_maa_slots_bound_member_id"), "maa_slots", ["bound_member_id"], unique=False
    )

    op.create_table(
        "maa_slot_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["slot_id"], ["maa_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_maa_slot_audits_slot_id"), "maa_slot_audits", ["slot_id"], unique=False
    )
    op.create_index(
        op.f("ix_maa_slot_audits_created_at"),
        "maa_slot_audits",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "maa_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["slot_id"], ["maa_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maa_jobs_slot_id"), "maa_jobs", ["slot_id"], unique=False)
    op.create_index(op.f("ix_maa_jobs_member_id"), "maa_jobs", ["member_id"], unique=False)
    op.create_index(op.f("ix_maa_jobs_status"), "maa_jobs", ["status"], unique=False)
