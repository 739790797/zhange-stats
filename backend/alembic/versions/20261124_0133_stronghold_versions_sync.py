"""Archive Stronghold versions and schedule durable syncs by bound role."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0133"
down_revision = "20261124_0132"
branch_labels = None
depends_on = None

_MATCHES = "arknights_stronghold_matches"
_RECORDS = "arknights_stronghold_records"
_TARGETS = "arknights_stronghold_sync_targets"
_ALIASES = "arknights_stronghold_record_aliases"


def _add_column(table, column):
    if all(existing["name"] != column.name for existing in sa.inspect(op.get_bind()).get_columns(table)):
        op.add_column(table, column)


def _create_index(name, table, columns, *, unique=False):
    if all(existing["name"] != name for existing in sa.inspect(op.get_bind()).get_indexes(table)):
        op.create_index(name, table, columns, unique=unique)


def _create_table(name, *columns):
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns)


def upgrade():
    # MariaDB DDL can commit before Alembic records the revision.
    _add_column(_MATCHES, sa.Column("scene_key", sa.String(64), nullable=True))
    _add_column(_MATCHES, sa.Column("version_id", sa.String(128), nullable=True))
    _create_index("uq_sh_match_scene_key", _MATCHES, ["scene_key"], unique=True)
    _create_index("ix_sh_match_version_ended", _MATCHES, ["season_id", "version_id", "ended_at"])
    # Keep identity_kind for legacy rows and downgrade compatibility. New writes use scene.
    _add_column(_RECORDS, sa.Column("snapshot_key", sa.String(64), nullable=True))
    _add_column(_RECORDS, sa.Column("version_id", sa.String(128), nullable=True))
    _create_table(
        _ALIASES,
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("record_id", sa.String(32), sa.ForeignKey(f"{_RECORDS}.id", ondelete="CASCADE"), nullable=False),
    )
    _create_index(f"ix_{_ALIASES}_record_id", _ALIASES, ["record_id"])
    _create_table(
        "arknights_stronghold_versions",
        sa.Column("season_id", sa.String(64), primary_key=True),
        sa.Column("version_id", sa.String(128), primary_key=True),
        sa.Column("label", sa.String(96), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("catalog", sa.JSON(), nullable=False),
        sa.Column("assets", sa.JSON(), nullable=False),
    )
    _create_table(
        "arknights_stronghold_activities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("resource_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_resource_at", sa.DateTime(timezone=True)),
    )
    _create_table(
        _TARGETS,
        sa.Column("bind_id", sa.Integer(), sa.ForeignKey("skland_binds.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", sa.String(8), primary_key=True),
        sa.Column("uid", sa.String(32), primary_key=True),
        sa.Column("binding_key", sa.String(64), nullable=False),
        sa.Column("role_name", sa.String(96), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("latest_battle_at", sa.DateTime(timezone=True)),
        sa.Column("requested", sa.Boolean(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    _create_index("ix_sh_sync_due", _TARGETS, ["due_at"])
    _create_table(
        "arknights_stronghold_sync_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("retry_until", sa.DateTime(timezone=True)),
        sa.Column("discovery_due_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("arknights_stronghold_sync_control")
    op.drop_table(_TARGETS)
    op.drop_table("arknights_stronghold_activities")
    op.drop_table("arknights_stronghold_versions")
    op.drop_table(_ALIASES)
    op.drop_column(_RECORDS, "version_id")
    op.drop_column(_RECORDS, "snapshot_key")
    op.drop_index("ix_sh_match_version_ended", table_name=_MATCHES)
    op.drop_index("uq_sh_match_scene_key", table_name=_MATCHES)
    op.drop_column(_MATCHES, "version_id")
    op.drop_column(_MATCHES, "scene_key")
