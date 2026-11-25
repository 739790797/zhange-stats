"""Add the Arknights Stronghold Protocol community data tables."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0130"
down_revision = "20261022_0129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "arknights_stronghold_roles" not in tables:
        op.create_table(
            "arknights_stronghold_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("bind_id", sa.Integer(), sa.ForeignKey("skland_binds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("channel_id", sa.String(8), nullable=False),
            sa.Column("uid", sa.String(32), nullable=False),
            sa.Column("role_name", sa.String(96), nullable=False),
            sa.Column("link_allowed", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("bind_id", "channel_id", "uid", name="uq_sh_role_bind_identity"),
            sqlite_autoincrement=True,
        )
    if "arknights_stronghold_matches" not in tables:
        op.create_table(
            "arknights_stronghold_matches",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("source_key", sa.String(64), unique=True, nullable=False),
            sa.Column("season_id", sa.String(64), nullable=False),
            sa.Column("season_label", sa.String(96), nullable=False),
            sa.Column("difficulty_id", sa.String(64), nullable=False),
            sa.Column("difficulty_label", sa.String(96), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("success", sa.Boolean(), nullable=False),
        )
    if "arknights_stronghold_participants" not in tables:
        op.create_table(
            "arknights_stronghold_participants",
            sa.Column(
                "match_id",
                sa.String(32),
                sa.ForeignKey("arknights_stronghold_matches.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("channel_id", sa.String(8), primary_key=True),
            sa.Column("uid", sa.String(32), primary_key=True),
        )
    if "arknights_stronghold_views" not in tables:
        op.create_table(
            "arknights_stronghold_views",
            sa.Column(
                "match_id",
                sa.String(32),
                sa.ForeignKey("arknights_stronghold_matches.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("arknights_stronghold_roles.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("shared", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        )

    for name, table, columns in (
        ("ix_sh_role_identity", "arknights_stronghold_roles", ["channel_id", "uid"]),
        ("ix_sh_match_scope_ended", "arknights_stronghold_matches", ["season_id", "difficulty_id", "ended_at"]),
        ("ix_sh_match_ended", "arknights_stronghold_matches", ["ended_at", "id"]),
        ("ix_sh_participant_identity", "arknights_stronghold_participants", ["channel_id", "uid"]),
        ("ix_sh_view_role", "arknights_stronghold_views", ["role_id"]),
    ):
        if name not in {index["name"] for index in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)


def downgrade() -> None:
    op.drop_table("arknights_stronghold_views")
    op.drop_table("arknights_stronghold_participants")
    op.drop_table("arknights_stronghold_matches")
    op.drop_table("arknights_stronghold_roles")
