"""Keep Stronghold history on the member and include all imported records in the diary."""

from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "20261124_0132"
down_revision = "20261124_0131"
branch_labels = None
depends_on = None

_ROLES = "arknights_stronghold_roles"
_MATCHES = "arknights_stronghold_matches"
_RECORDS = "arknights_stronghold_records"
_BONDS = "arknights_stronghold_view_bonds"
_VIEWS = "arknights_stronghold_views"
_ALIASES = "arknights_stronghold_match_aliases"
_BIND_UQ = "uq_sh_role_bind_identity"
_MEMBER_UQ = "uq_sh_role_member_identity"
_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s"}


def _columns(table):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _foreign_key(table, column):
    for fk in sa.inspect(op.get_bind()).get_foreign_keys(table):
        if fk["constrained_columns"] == [column]:
            return fk["name"] or f"fk_{table}_{column}"
    return None


def _add_column(table, column):
    if column.name not in _columns(table):
        op.add_column(table, column)


def _bind_roles_to_members():
    conn = op.get_bind()
    _add_column(_ROLES, sa.Column("member_id", sa.Integer()))
    if "bind_id" in _columns(_ROLES):
        roles = sa.table(_ROLES, sa.column("bind_id"), sa.column("member_id"))
        binds = sa.table("skland_binds", sa.column("id"), sa.column("member_id"))
        conn.execute(
            roles.update()
            .where(roles.c.member_id.is_(None))
            .values(member_id=sa.select(binds.c.member_id).where(binds.c.id == roles.c.bind_id).scalar_subquery())
        )
    constraints = {u["name"] for u in sa.inspect(conn).get_unique_constraints(_ROLES)}
    bind_fk = _foreign_key(_ROLES, "bind_id")
    member_fk = _foreign_key(_ROLES, "member_id")
    columns = _columns(_ROLES)
    with op.batch_alter_table(_ROLES, naming_convention=_NAMING, table_kwargs={"sqlite_autoincrement": True}) as batch:
        if bind_fk:
            batch.drop_constraint(bind_fk, type_="foreignkey")
        if _BIND_UQ in constraints:
            batch.drop_constraint(_BIND_UQ, type_="unique")
        if "bind_id" in columns:
            batch.drop_column("bind_id")
        if "link_allowed" in columns:
            batch.drop_column("link_allowed")
        batch.alter_column("member_id", existing_type=sa.Integer(), nullable=False)
        if _MEMBER_UQ not in constraints:
            batch.create_unique_constraint(_MEMBER_UQ, ["member_id", "channel_id", "uid"])
        if member_fk is None:
            batch.create_foreign_key("fk_sh_role_member", "members", ["member_id"], ["id"], ondelete="CASCADE")


def _attach_existing_records():
    conn = op.get_bind()
    metadata = sa.MetaData()
    records, roles, matches = [
        sa.Table(t, metadata, autoload_with=conn, resolve_fks=False) for t in (_RECORDS, _ROLES, _MATCHES)
    ]
    fields = ("season_id", "season_label", "difficulty_id", "difficulty_label", "ended_at", "mode_type")
    rows = (
        conn.execute(
            sa.select(
                records.c.id,
                records.c.source_view_key,
                roles.c.channel_id,
                roles.c.uid,
                *[records.c[f] for f in fields],
            )
            .join(roles, roles.c.id == records.c.role_id)
            .where(records.c.match_id.is_(None))
            .order_by(records.c.ended_at.desc(), records.c.id)
        )
        .mappings()
        .all()
    )
    new_matches = {}
    links = []
    for row in rows:
        digest = sha256(
            f"view:{row['season_id']}:{row['channel_id']}:{row['uid']}:{row['source_view_key'] or row['id']}".encode()
        ).hexdigest()
        match_id = uuid5(NAMESPACE_URL, f"zhange:stronghold:provisional:{digest}").hex
        new_matches.setdefault(
            digest,
            {
                **{f: row[f] for f in fields},
                "id": match_id,
                "source_key": digest,
                "identity_kind": "record",
                "success": False,
            },
        )
        links.append({"record_id": row["id"], "match_id": match_id})
    if new_matches:
        existing = set(conn.scalars(sa.select(matches.c.source_key).where(matches.c.identity_kind == "record")))
        inserts = [row for key, row in new_matches.items() if key not in existing]
        if inserts:
            conn.execute(matches.insert(), inserts)
        conn.execute(records.update().where(records.c.id == sa.bindparam("record_id")), links)


def upgrade():
    conn = op.get_bind()
    _add_column(_MATCHES, sa.Column("identity_kind", sa.String(16), nullable=False, server_default="verified"))
    _add_column(_RECORDS, sa.Column("details", sa.JSON(none_as_null=True)))
    _add_column(_BONDS, sa.Column("icon_url", sa.String(512)))
    _bind_roles_to_members()
    _attach_existing_records()
    if not sa.inspect(conn).has_table(_ALIASES):
        op.create_table(
            _ALIASES,
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("match_id", sa.String(32), sa.ForeignKey(f"{_MATCHES}.id", ondelete="CASCADE"), nullable=False),
        )
    if f"ix_{_ALIASES}_match_id" not in {i["name"] for i in sa.inspect(conn).get_indexes(_ALIASES)}:
        op.create_index(f"ix_{_ALIASES}_match_id", _ALIASES, ["match_id"])
    record_fk = _foreign_key(_RECORDS, "match_id")
    if record_fk != "fk_sh_record_match":
        with op.batch_alter_table(_RECORDS, naming_convention=_NAMING) as batch:
            if record_fk:
                batch.drop_constraint(record_fk, type_="foreignkey")
            batch.alter_column("match_id", existing_type=sa.String(32), nullable=False)
            batch.create_foreign_key("fk_sh_record_match", _MATCHES, ["match_id"], ["id"], ondelete="CASCADE")
    if sa.inspect(conn).has_table(_VIEWS):
        op.drop_table(_VIEWS)


def downgrade():
    conn = op.get_bind()
    roles = sa.table(_ROLES, sa.column("member_id"))
    binds = sa.table("skland_binds", sa.column("id"), sa.column("member_id"))
    matches = sa.table(_MATCHES, sa.column("identity_kind"))
    aliases = sa.table(_ALIASES, sa.column("id"))
    unbound = (
        sa.select(1).select_from(roles).where(~sa.exists(sa.select(1).where(binds.c.member_id == roles.c.member_id)))
    )
    if any(
        conn.scalar(stmt.limit(1))
        for stmt in (
            unbound,
            sa.select(1).select_from(matches).where(matches.c.identity_kind != "verified"),
            sa.select(1).select_from(aliases),
        )
    ):
        raise RuntimeError("Use a pre-migration backup to downgrade persisted Stronghold history")
    op.create_table(
        _VIEWS,
        sa.Column("match_id", sa.String(32), sa.ForeignKey(f"{_MATCHES}.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey(f"{_ROLES}.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("shared", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("ix_sh_view_role", _VIEWS, ["role_id"])
    records = sa.table(_RECORDS, sa.column("match_id"), sa.column("role_id"))
    views = sa.table(_VIEWS, sa.column("match_id"), sa.column("role_id"))
    conn.execute(views.insert().from_select(["match_id", "role_id"], sa.select(records.c.match_id, records.c.role_id)))
    op.drop_table(_ALIASES)
    op.drop_column(_BONDS, "icon_url")
    with op.batch_alter_table(_RECORDS, naming_convention=_NAMING) as batch:
        batch.drop_constraint("fk_sh_record_match", type_="foreignkey")
        batch.alter_column("match_id", existing_type=sa.String(32), nullable=True)
        batch.create_foreign_key("fk_sh_record_match_old", _MATCHES, ["match_id"], ["id"], ondelete="SET NULL")
        batch.drop_column("details")
    op.drop_column(_MATCHES, "identity_kind")
    op.add_column(_ROLES, sa.Column("bind_id", sa.Integer()))
    roles.append_column(sa.column("bind_id"))
    conn.execute(
        roles.update().values(
            bind_id=sa.select(binds.c.id).where(binds.c.member_id == roles.c.member_id).scalar_subquery()
        )
    )
    with op.batch_alter_table(_ROLES, naming_convention=_NAMING, table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_constraint("fk_sh_role_member", type_="foreignkey")
        batch.drop_constraint(_MEMBER_UQ, type_="unique")
        batch.drop_column("member_id")
        batch.add_column(sa.Column("link_allowed", sa.Boolean(), server_default=sa.text("0"), nullable=False))
        batch.alter_column("bind_id", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(_BIND_UQ, ["bind_id", "channel_id", "uid"])
        batch.create_foreign_key("fk_sh_role_bind_old", "skland_binds", ["bind_id"], ["id"], ondelete="CASCADE")
