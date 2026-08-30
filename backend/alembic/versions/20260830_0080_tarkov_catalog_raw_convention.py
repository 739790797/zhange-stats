"""Unify tarkov catalog raw tables: one upstream file per table.

Revision ID: 20260830_0080
Revises: 20260830_0079
Create Date: 2026-08-30

MariaDB: inspect-gated DDL; JSON split is done in Python, not CAST(... AS JSON).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0080"
down_revision: Union[str, Sequence[str], None] = "20260830_0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RAW_TABLES = (
    ("tarkov_items_raws", "uq_tarkov_items_raws_mode_lang"),
    ("tarkov_maps_raws", "uq_tarkov_maps_raws_mode_lang"),
    ("tarkov_tasks_raws", "uq_tarkov_tasks_raws_mode_lang"),
    ("tarkov_traders_raws", "uq_tarkov_traders_raws_mode_lang"),
    ("tarkov_hideout_raws", "uq_tarkov_hideout_raws_mode_lang"),
    ("tarkov_barters_raws", "uq_tarkov_barters_raws_mode_lang"),
    ("tarkov_crafts_raws", "uq_tarkov_crafts_raws_mode_lang"),
    ("tarkov_extras_raws", "uq_tarkov_extras_raws_mode_lang"),
)
_EXISTING_RAW = ("tarkov_items_raws", "tarkov_tasks_raws", "tarkov_traders_raws")
_NEW_RAW = (
    "tarkov_maps_raws",
    "tarkov_hideout_raws",
    "tarkov_barters_raws",
    "tarkov_crafts_raws",
    "tarkov_extras_raws",
)
_DROP_TABLES = (
    "tarkov_items_meta",
    "tarkov_ammo_meta",
    "tarkov_gun_meta",
    "tarkov_tasks_meta",
    "tarkov_traders_meta",
    "tarkov_bosses_meta",
    "tarkov_guides_meta",
    "tarkov_upstream_raws",
    "tarkov_bosses_raws",
    "tarkov_guides_raws",
)
_UPSTREAM_MAP = {
    "items": ("tarkov_items_raws", ""),
    "items_zh": ("tarkov_items_raws", "zh"),
    "maps": ("tarkov_maps_raws", ""),
    "maps_zh": ("tarkov_maps_raws", "zh"),
    "tasks": ("tarkov_tasks_raws", ""),
    "tasks_zh": ("tarkov_tasks_raws", "zh"),
    "traders": ("tarkov_traders_raws", ""),
    "traders_zh": ("tarkov_traders_raws", "zh"),
    "hideout": ("tarkov_hideout_raws", ""),
    "hideout_zh": ("tarkov_hideout_raws", "zh"),
    "barters": ("tarkov_barters_raws", ""),
    "crafts": ("tarkov_crafts_raws", ""),
    "extras": ("tarkov_extras_raws", ""),
}


def _inspect():
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspect().get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {col["name"] for col in _inspect().get_columns(table)}


def _unique_names(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {uq.get("name") for uq in _inspect().get_unique_constraints(table) if uq.get("name")}


def _pk_cols(table: str) -> list[str]:
    if table not in _tables():
        return []
    pk = _inspect().get_pk_constraint(table) or {}
    return list(pk.get("constrained_columns") or [])


def _create_raw_table(table: str, uq_name: str) -> None:
    if table in _tables():
        return
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mode_id", sa.Integer(), nullable=False),
        sa.Column("lang", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.Text(length=4294967295), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode_id", "lang", name=uq_name),
    )


def _upgrade_existing_raw(table: str, uq_name: str) -> None:
    if table not in _tables():
        _create_raw_table(table, uq_name)
        return
    cols = _columns(table)
    if "mode_id" not in cols:
        op.add_column(table, sa.Column("mode_id", sa.Integer(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET mode_id = id"))
        op.alter_column(table, "mode_id", existing_type=sa.Integer(), nullable=False)
    if "lang" not in _columns(table):
        op.add_column(
            table,
            sa.Column("lang", sa.String(length=8), nullable=False, server_default=""),
        )
    if uq_name not in _unique_names(table):
        op.create_unique_constraint(uq_name, table, ["mode_id", "lang"])
    op.execute(sa.text(f"ALTER TABLE {table} MODIFY id INT NOT NULL AUTO_INCREMENT"))


def _fetch_raw_row(table: str, mode_id: int, lang: str) -> Any:
    return (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT id, synced_at FROM {table} WHERE mode_id = :mode_id AND lang = :lang"
            ),
            {"mode_id": mode_id, "lang": lang},
        )
        .fetchone()
    )


def _upsert_raw(
    table: str,
    *,
    mode_id: int,
    lang: str,
    source: str,
    raw_json: str,
    synced_at: datetime | None,
    note: str | None,
) -> None:
    if table not in _tables():
        return
    existing = _fetch_raw_row(table, mode_id, lang)
    if existing is not None:
        old_synced = existing[1]
        if old_synced is not None and synced_at is not None and old_synced >= synced_at:
            return
        op.get_bind().execute(
            sa.text(
                f"UPDATE {table} SET source = :source, raw_json = :raw_json, "
                "synced_at = :synced_at, note = :note "
                "WHERE mode_id = :mode_id AND lang = :lang"
            ),
            {
                "source": source,
                "raw_json": raw_json,
                "synced_at": synced_at,
                "note": note,
                "mode_id": mode_id,
                "lang": lang,
            },
        )
        return
    op.get_bind().execute(
        sa.text(
            f"INSERT INTO {table} (mode_id, lang, source, raw_json, synced_at, note) "
            "VALUES (:mode_id, :lang, :source, :raw_json, :synced_at, :note)"
        ),
        {
            "mode_id": mode_id,
            "lang": lang,
            "source": source,
            "raw_json": raw_json,
            "synced_at": synced_at,
            "note": note,
        },
    )


def _copy_bosses_to_maps() -> None:
    if "tarkov_bosses_raws" not in _tables() or "tarkov_maps_raws" not in _tables():
        return
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id, source, raw_json, synced_at, note FROM tarkov_bosses_raws"
            )
        )
        .fetchall()
    )
    for row in rows:
        _upsert_raw(
            "tarkov_maps_raws",
            mode_id=int(row[0]),
            lang="",
            source=row[1],
            raw_json=row[2],
            synced_at=row[3],
            note=row[4],
        )


def _split_guides() -> None:
    if "tarkov_guides_raws" not in _tables():
        return
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id, source, raw_json, synced_at, note FROM tarkov_guides_raws"
            )
        )
        .fetchall()
    )
    for row in rows:
        mode_id = int(row[0])
        source = row[1]
        raw_json = row[2]
        synced_at = row[3]
        note = row[4]
        hideout: Any = None
        barters: Any = None
        crafts: Any = None
        locale: Any = None
        try:
            payload = json.loads(raw_json)
        except (TypeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("hideout"), dict):
            hideout = payload["hideout"]
            barters = payload.get("barters")
            crafts = payload.get("crafts")
            locale = payload.get("locale")
        else:
            hideout = payload if isinstance(payload, dict) else None
        if hideout is None:
            hideout_json = raw_json
        else:
            hideout_json = json.dumps(
                hideout if isinstance(hideout.get("data"), (dict, list)) else {"data": hideout},
                ensure_ascii=False,
            ) if isinstance(hideout, dict) else raw_json
        _upsert_raw(
            "tarkov_hideout_raws",
            mode_id=mode_id,
            lang="",
            source=source,
            raw_json=hideout_json,
            synced_at=synced_at,
            note=note,
        )
        if isinstance(barters, list):
            _upsert_raw(
                "tarkov_barters_raws",
                mode_id=mode_id,
                lang="",
                source=source,
                raw_json=json.dumps({"data": barters}, ensure_ascii=False),
                synced_at=synced_at,
                note=note,
            )
        if isinstance(crafts, list):
            _upsert_raw(
                "tarkov_crafts_raws",
                mode_id=mode_id,
                lang="",
                source=source,
                raw_json=json.dumps({"data": crafts}, ensure_ascii=False),
                synced_at=synced_at,
                note=note,
            )
        if isinstance(locale, dict) and locale:
            _upsert_raw(
                "tarkov_hideout_raws",
                mode_id=mode_id,
                lang="zh",
                source=source,
                raw_json=json.dumps(locale, ensure_ascii=False),
                synced_at=synced_at,
                note=note,
            )


def _copy_upstream() -> None:
    if "tarkov_upstream_raws" not in _tables():
        return
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT mode_id, resource, source, raw_json, synced_at, note "
                "FROM tarkov_upstream_raws"
            )
        )
        .fetchall()
    )
    for row in rows:
        mapped = _UPSTREAM_MAP.get(str(row[1] or ""))
        if mapped is None:
            continue
        table, lang = mapped
        _upsert_raw(
            table,
            mode_id=int(row[0]),
            lang=lang,
            source=row[2],
            raw_json=row[3],
            synced_at=row[4],
            note=row[5],
        )


def _upgrade_derived(table: str) -> None:
    if table not in _tables():
        return
    if "mode_id" not in _columns(table):
        op.add_column(table, sa.Column("mode_id", sa.Integer(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET mode_id = 1 WHERE mode_id IS NULL"))
        op.alter_column(table, "mode_id", existing_type=sa.Integer(), nullable=False)
    if _pk_cols(table) == ["item_id"]:
        op.execute(sa.text(f"ALTER TABLE {table} DROP PRIMARY KEY"))
        op.create_primary_key(f"pk_{table}", table, ["mode_id", "item_id"])


def upgrade() -> None:
    for table in _NEW_RAW:
        uq_name = next(uq for name, uq in _RAW_TABLES if name == table)
        _create_raw_table(table, uq_name)
    for table in _EXISTING_RAW:
        uq_name = next(uq for name, uq in _RAW_TABLES if name == table)
        _upgrade_existing_raw(table, uq_name)
    _copy_bosses_to_maps()
    _split_guides()
    _copy_upstream()
    _upgrade_derived("tarkov_ammo")
    _upgrade_derived("tarkov_guns")
    tables = _tables()
    for table in _DROP_TABLES:
        if table in tables:
            op.drop_table(table)


def downgrade() -> None:
    tables = _tables()
    for table in _NEW_RAW:
        if table in tables:
            op.drop_table(table)
    for table in ("tarkov_ammo", "tarkov_guns"):
        if table not in _tables() or "mode_id" not in _columns(table):
            continue
        if _pk_cols(table) == ["mode_id", "item_id"]:
            op.execute(sa.text(f"ALTER TABLE {table} DROP PRIMARY KEY"))
            op.create_primary_key(f"pk_{table}_item_id", table, ["item_id"])
        op.drop_column(table, "mode_id")
    for table in _EXISTING_RAW:
        if table not in _tables():
            continue
        uq_name = next(uq for name, uq in _RAW_TABLES if name == table)
        if uq_name in _unique_names(table):
            op.drop_constraint(uq_name, table, type_="unique")
        cols = _columns(table)
        if "lang" in cols:
            op.drop_column(table, "lang")
        if "mode_id" in cols:
            op.drop_column(table, "mode_id")
