"""Add Steam calendar composite indexes and job_runs.started_at index.

Revision ID: 20260805_0018
Revises: 20260805_0017
Create Date: 2026-08-05

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260805_0018"
down_revision: Union[str, Sequence[str], None] = "20260805_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_play_sessions_member_started",
        "play_sessions",
        ["member_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_play_sessions_member_ended",
        "play_sessions",
        ["member_id", "ended_at"],
        unique=False,
    )
    op.create_index(
        "ix_presence_segments_member_started",
        "presence_segments",
        ["member_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_presence_segments_member_ended",
        "presence_segments",
        ["member_id", "ended_at"],
        unique=False,
    )
    op.create_index(
        "ix_job_runs_started_at",
        "job_runs",
        ["started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_runs_started_at", table_name="job_runs")
    op.drop_index(
        "ix_presence_segments_member_ended", table_name="presence_segments"
    )
    op.drop_index(
        "ix_presence_segments_member_started", table_name="presence_segments"
    )
    op.drop_index("ix_play_sessions_member_ended", table_name="play_sessions")
    op.drop_index("ix_play_sessions_member_started", table_name="play_sessions")
