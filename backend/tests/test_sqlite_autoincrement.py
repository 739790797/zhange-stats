"""SQLite: create_all databases never hand a deleted users / members / articles id out again."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.database import Base, _build_engine
from app.core.migrate import _BACKEND_ROOT
from app.models.articles import Article
from app.models.member import Member
from app.models.user import User

# Migrations up to here never run on a database that create_all built with AUTOINCREMENT.
_LAST_REVIEWED_REVISION = "20261010_0121"

_FACTORIES = {
    "users": lambda n: User(username=f"u{n}", display_name=f"U{n}", password_hash="x"),
    "members": lambda n: Member(nickname=f"m{n}"),
    "articles": lambda n: Article(slug=f"a{n}", title=f"A{n}"),
}


def _autoincrement_tables() -> set[str]:
    tables = Base.metadata.sorted_tables
    return {t.name for t in tables if t.dialect_options["sqlite"]["autoincrement"]}


def test_externally_referenced_tables_use_autoincrement() -> None:
    assert _autoincrement_tables() == set(_FACTORIES)


@pytest.mark.parametrize("table", sorted(_FACTORIES))
def test_deleted_highest_id_is_not_handed_out_again(tmp_path: Path, table: str) -> None:
    engine = _build_engine(f"sqlite:///{tmp_path / 'zhange.sqlite'}")
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            ddl = conn.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).scalar_one()
        assert "AUTOINCREMENT" in ddl

        make = _FACTORIES[table]
        with Session(engine) as db:
            kept, deleted = make(1), make(2)
            db.add_all([kept, deleted])
            db.commit()
            freed = deleted.id
            db.delete(deleted)
            db.commit()
            newcomer = make(3)
            db.add(newcomer)
            db.commit()
            assert newcomer.id > freed
    finally:
        engine.dispose()


def _batch_rebuilds_without_autoincrement(source: str, tables: set[str]) -> list[int]:
    """Reflection drops AUTOINCREMENT, so a batch rebuild keeps it only through table_kwargs."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        first = node.args[0]
        if name != "batch_alter_table" or not (
            isinstance(first, ast.Constant) and first.value in tables
        ):
            continue
        kwargs = next((kw.value for kw in node.keywords if kw.arg == "table_kwargs"), None)
        if kwargs is None or "sqlite_autoincrement" not in ast.unparse(kwargs):
            lines.append(node.lineno)
    return lines


def test_guard_spots_batch_rebuilds_that_drop_autoincrement() -> None:
    source = (
        'with op.batch_alter_table("users") as batch:\n    pass\n'
        'with op.batch_alter_table("users", table_kwargs={"sqlite_autoincrement": True}) as b:\n'
        "    pass\n"
        'with op.batch_alter_table("job_runs") as batch:\n    pass\n'
    )
    assert _batch_rebuilds_without_autoincrement(source, {"users"}) == [1]


def test_later_migrations_keep_autoincrement_when_rebuilding() -> None:
    tables = _autoincrement_tables()
    offenders = [
        f"{path.name}:{line}"
        for path in sorted((_BACKEND_ROOT / "alembic" / "versions").glob("*.py"))
        if path.stem[:13] > _LAST_REVIEWED_REVISION
        for line in _batch_rebuilds_without_autoincrement(path.read_text(encoding="utf-8"), tables)
    ]
    assert offenders == []
