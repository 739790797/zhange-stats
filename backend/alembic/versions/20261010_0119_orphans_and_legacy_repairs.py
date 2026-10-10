"""SQLite FK orphan cleanup; legacy schema repairs moved off the boot path.

Revision ID: 20261010_0119
Revises: 20261010_0118
Create Date: 2026-10-10

- SQLite ran with foreign keys off until the app engine started enforcing them, so deleted
  parents (members, users, binds, rooms, articles, ...) left child rows behind and a reused id
  could inherit them. Remove those orphans following each FK's declared ON DELETE action
  (CASCADE -> delete, SET NULL -> clear). MariaDB enforces FKs, so this step is SQLite-only.
- register_challenges without ``purpose`` / with a non-(email, purpose) PK (v0.2.37 dual-0056
  collision) is rebuilt by copying rows, not dropped. minecraft_server_profiles public_* is
  copied into system_configs ``integrations`` before the columns go. Both used to run on
  every MySQL boot.
- create_all-era SQLite databases lack the arknights_operators indexes 0010 created.

MariaDB note: DDL is non-transactional; every step is gated on inspect so a half-applied
upgrade can be re-run. Downgrade is a no-op (data cleanup and repairs are not reversible).
"""

from __future__ import annotations

import json
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0119"
down_revision: Union[str, Sequence[str], None] = "20261010_0118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("zhange.migrate")

_CHUNK = 500
# FK chains are at most users -> members -> binds -> logs; each pass clears one level
_MAX_ORPHAN_PASSES = 10
_RC = "register_challenges"
_RC_REBUILD = "_register_challenges_rebuild"


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _cascade_fks(bind) -> list[tuple[str, str, str, str, str]]:
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    out: list[tuple[str, str, str, str, str]] = []
    for table in sorted(tables):
        nullable = {c["name"]: bool(c.get("nullable")) for c in insp.get_columns(table)}
        for fk in insp.get_foreign_keys(table):
            cols = fk.get("constrained_columns") or []
            refs = fk.get("referred_columns") or []
            parent = fk.get("referred_table")
            action = str((fk.get("options") or {}).get("ondelete") or "").upper()
            if len(cols) != 1 or len(refs) != 1 or parent not in tables:
                continue
            if action == "SET NULL" and not nullable.get(cols[0], False):
                continue
            if action in ("CASCADE", "SET NULL"):
                out.append((table, cols[0], parent, refs[0], action))
    return out


def _orphan_keys(bind, table: str, col: str, parent: str, ref: str) -> list:
    child = sa.table(table, sa.column(col)).alias("child")
    par = sa.table(parent, sa.column(ref)).alias("parent")
    stmt = (
        sa.select(child.c[col])
        .where(child.c[col].is_not(None))
        .where(~sa.exists().where(par.c[ref] == child.c[col]))
        .distinct()
    )
    return [row[0] for row in bind.execute(stmt)]


def _clean_sqlite_orphans(bind) -> None:
    fks = _cascade_fks(bind)
    for _ in range(_MAX_ORPHAN_PASSES):
        changed = False
        for table, col, parent, ref, action in fks:
            keys = _orphan_keys(bind, table, col, parent, ref)
            if not keys:
                continue
            target = sa.table(table, sa.column(col))
            removed = 0
            for start in range(0, len(keys), _CHUNK):
                chunk = keys[start : start + _CHUNK]
                if action == "CASCADE":
                    stmt = sa.delete(target).where(target.c[col].in_(chunk))
                else:
                    stmt = sa.update(target).where(target.c[col].in_(chunk)).values({col: None})
                removed += bind.execute(stmt).rowcount or 0
            logger.warning(
                "orphan cleanup: %s %s rows of %s whose %s.%s is gone",
                "deleted" if action == "CASCADE" else "cleared",
                removed,
                table,
                parent,
                ref,
            )
            changed = True
        if not changed:
            return


def _ensure_register_challenges_index(bind) -> None:
    existing = {ix["name"] for ix in sa.inspect(bind).get_indexes(_RC)}
    if "ix_register_challenges_expires_at" not in existing:
        op.create_index("ix_register_challenges_expires_at", _RC, ["expires_at"])


def _repair_register_challenges(bind) -> None:
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if _RC not in tables:
        # A MariaDB run that died between DROP and RENAME left the copied rows here.
        if _RC_REBUILD in tables:
            op.rename_table(_RC_REBUILD, _RC)
            _ensure_register_challenges_index(bind)
        return
    cols = {c["name"] for c in insp.get_columns(_RC)}
    pk_cols = set((insp.get_pk_constraint(_RC) or {}).get("constrained_columns") or [])
    if "purpose" in cols and pk_cols == {"email", "purpose"}:
        _ensure_register_challenges_index(bind)
        return

    logger.warning("rebuilding register_challenges with (email, purpose) primary key")
    if _RC_REBUILD in tables:
        op.drop_table(_RC_REBUILD)
    op.create_table(
        _RC_REBUILD,
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("email", "purpose"),
    )
    old = sa.table(_RC, *(sa.column(name) for name in sorted(cols)))
    new = sa.table(
        _RC_REBUILD,
        sa.column("email"),
        sa.column("purpose"),
        sa.column("code"),
        sa.column("expires_at"),
        sa.column("attempts"),
    )
    # Legacy rows predate purposes; they were registration codes.
    purpose = old.c.purpose if "purpose" in cols else sa.literal("register")
    attempts = old.c.attempts if "attempts" in cols else sa.literal(0)
    bind.execute(
        new.insert().from_select(
            ["email", "purpose", "code", "expires_at", "attempts"],
            sa.select(old.c.email, purpose, old.c.code, old.c.expires_at, attempts),
        )
    )
    op.drop_table(_RC)
    op.rename_table(_RC_REBUILD, _RC)
    _ensure_register_challenges_index(bind)


def _copy_minecraft_public_address(bind) -> None:
    profiles = sa.table(
        "minecraft_server_profiles",
        sa.column("id"),
        sa.column("public_host"),
        sa.column("public_port"),
    )
    row = bind.execute(
        sa.select(profiles.c.public_host, profiles.c.public_port).where(profiles.c.id == 1)
    ).first()
    if row is None:
        return
    host = (row.public_host or "").strip()
    try:
        port = int(row.public_port or 25565)
    except (TypeError, ValueError):
        port = 25565
    if port < 1 or port > 65535:
        port = 25565
    if not host and port == 25565:
        return

    configs = sa.table("system_configs", sa.column("key"), sa.column("value"))
    current = bind.execute(
        sa.select(configs.c.value).where(configs.c.key == "integrations")
    ).first()
    stored: dict = {}
    if current is not None:
        try:
            parsed = json.loads(current.value or "{}")
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            stored = parsed
    if host:
        stored.setdefault("minecraft_public_host", host)
    stored.setdefault("minecraft_public_port", port)
    payload = json.dumps(stored, ensure_ascii=False)
    if current is None:
        bind.execute(configs.insert().values(key="integrations", value=payload))
    else:
        bind.execute(
            configs.update().where(configs.c.key == "integrations").values(value=payload)
        )


def _repair_minecraft_public_columns(bind) -> None:
    tables = _tables(bind)
    if "minecraft_server_profiles" not in tables:
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("minecraft_server_profiles")}
    stale = [name for name in ("public_host", "public_port") if name in cols]
    if not stale:
        return
    logger.warning("moving minecraft_server_profiles public_* into system_configs integrations")
    if len(stale) == 2 and "system_configs" in tables:
        _copy_minecraft_public_address(bind)
    with op.batch_alter_table("minecraft_server_profiles") as batch:
        for name in stale:
            batch.drop_column(name)


def _ensure_arknights_operator_indexes(bind) -> None:
    if "arknights_operators" not in _tables(bind):
        return
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("arknights_operators")}
    existing = {ix["name"] for ix in insp.get_indexes("arknights_operators")}
    for col in ("profession", "rarity"):
        name = f"ix_arknights_operators_{col}"
        if col in cols and name not in existing:
            op.create_index(name, "arknights_operators", [col])


def upgrade() -> None:
    bind = op.get_bind()
    _repair_register_challenges(bind)
    _repair_minecraft_public_columns(bind)
    _ensure_arknights_operator_indexes(bind)
    if bind.dialect.name == "sqlite":
        _clean_sqlite_orphans(bind)


def downgrade() -> None:
    pass
