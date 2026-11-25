"""Store private Stronghold perspectives and their normalized bond values."""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "20261124_0131"
down_revision = "20261124_0130"
branch_labels = None
depends_on = None

_MATCHES = "arknights_stronghold_matches"
_VIEWS = "arknights_stronghold_views"
_RECORDS = "arknights_stronghold_records"
_BONDS = "arknights_stronghold_view_bonds"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "mode_type" not in {column["name"] for column in inspector.get_columns(_MATCHES)}:
        op.add_column(_MATCHES, sa.Column("mode_type", sa.String(16)))
    if not inspector.has_table(_RECORDS):
        op.create_table(
            _RECORDS,
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey("arknights_stronghold_roles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("match_id", sa.String(32), sa.ForeignKey(f"{_MATCHES}.id", ondelete="SET NULL")),
            sa.Column("source_view_key", sa.String(64)),
            sa.Column("season_id", sa.String(64), nullable=False),
            sa.Column("season_label", sa.String(96), nullable=False),
            sa.Column("difficulty_id", sa.String(64), nullable=False),
            sa.Column("difficulty_label", sa.String(96), nullable=False),
            sa.Column("mode_type", sa.String(16)),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("complete_state", sa.Boolean()),
            sa.Column("pass_round", sa.Integer()),
            sa.Column("strategy_id", sa.String(128)),
            sa.Column("strategy_name", sa.String(96)),
            sa.Column("roster", sa.JSON(none_as_null=True)),
            sa.Column("bonds_known", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.UniqueConstraint("role_id", "season_id", "source_view_key", name="uq_sh_record_role_source"),
            sa.UniqueConstraint("match_id", "role_id", name="uq_sh_record_match_role"),
        )
    if "ix_sh_record_role_ended" not in {idx["name"] for idx in inspector.get_indexes(_RECORDS)}:
        op.create_index("ix_sh_record_role_ended", _RECORDS, ["role_id", "ended_at", "id"])
    if not inspector.has_table(_BONDS):
        op.create_table(
            _BONDS,
            sa.Column("view_id", sa.String(32), sa.ForeignKey(f"{_RECORDS}.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("bond_id", sa.String(128), primary_key=True),
            sa.Column("name", sa.String(96)),
            sa.Column("active", sa.Boolean()),
            sa.Column("layer", sa.Integer()),
            sa.Column("layer_scope", sa.String(16)),
        )

    # Fill only the missing links, without turning a legacy team result into a personal result.
    metadata = sa.MetaData()
    matches = sa.Table(_MATCHES, metadata, autoload_with=bind, resolve_fks=False)
    views = sa.Table(_VIEWS, metadata, autoload_with=bind, resolve_fks=False)
    records = sa.Table(_RECORDS, metadata, autoload_with=bind, resolve_fks=False)
    fields = [
        matches.c[name] for name in ("season_id", "season_label", "difficulty_id", "difficulty_label", "ended_at")
    ]
    missing = (
        bind.execute(
            sa.select(views.c.match_id, views.c.role_id, *fields)
            .select_from(views.join(matches, views.c.match_id == matches.c.id))
            .where(
                ~sa.exists(
                    sa.select(1).where(records.c.match_id == views.c.match_id, records.c.role_id == views.c.role_id)
                )
            )
        )
        .mappings()
        .all()
    )
    if missing:
        bind.execute(
            records.insert(),
            [
                dict(row, id=uuid5(NAMESPACE_URL, f"zhange:stronghold:{row['match_id']}:{row['role_id']}").hex)
                for row in missing
            ],
        )


def downgrade() -> None:
    op.drop_table(_BONDS)
    op.drop_table(_RECORDS)
    op.drop_column(_MATCHES, "mode_type")
