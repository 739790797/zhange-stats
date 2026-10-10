"""time_storage marker: schemas built from empty are Beijing wall clock; only UTC-era data is shifted."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core import beijing_time_migrate as btm
from app.core import database as dbmod
from app.core import migrate
from app.core.config import get_settings
from app.core.database import Base, configure_engine
from app.models.job_run import JobRun
from app.models.system_config import SystemConfig

_STARTED = datetime(2026, 7, 31, 16, 0)


def _marker(engine) -> str | None:
    with Session(engine) as db:
        row = db.get(SystemConfig, "time_storage")
        return row.value if row is not None else None


def _set_revision(engine, revision: str) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        conn.exec_driver_sql("DELETE FROM alembic_version")
        conn.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES (?)", (revision,))


@pytest.fixture
def sqlite_app_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'zhange.sqlite'}")
    get_settings.cache_clear()
    engine = configure_engine()
    try:
        yield engine
    finally:
        engine.dispose()
        dbmod._engine = None
        dbmod._SessionLocal = None
        get_settings.cache_clear()


def test_fresh_sqlite_is_marked_beijing(sqlite_app_db) -> None:
    migrate.run_migrations()
    assert _marker(sqlite_app_db) == "beijing_v1"

    migrate.run_migrations()
    assert _marker(sqlite_app_db) == "beijing_v1"


def test_unmarked_sqlite_is_never_shifted(sqlite_app_db) -> None:
    Base.metadata.create_all(sqlite_app_db)
    with Session(sqlite_app_db) as db:
        db.add(JobRun(job_key="probe", started_at=_STARTED, status="ok"))
        db.commit()
        btm.ensure_beijing_time_storage(db, sqlite_app_db)
        assert db.get(SystemConfig, "time_storage").value == "beijing_v1"
        assert db.query(JobRun.started_at).scalar() == _STARTED


def _step(*sources: str, is_stamp: bool = False) -> SimpleNamespace:
    return SimpleNamespace(is_upgrade=True, is_stamp=is_stamp, source_revision_ids=sources)


def _apply(hook: btm.UtcEraUpgradeMarker, conn, step: SimpleNamespace) -> None:
    hook(ctx=SimpleNamespace(as_sql=False, connection=conn), step=step, heads=set(), run_args={})


class _FakeAlembic:
    """Stand-in for alembic.command: the server branch is pure orchestration around it.

    upgrade() runs the env.py hook for the first step, as a real run would.
    """

    def __init__(self, engine, head: str) -> None:
        self.engine = engine
        self.head = head
        self.calls: list[str] = []

    def upgrade(self, cfg, target) -> None:
        self.calls.append(f"upgrade {target}")
        source = btm.current_revision(self.engine)
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            _apply(btm.UtcEraUpgradeMarker(), conn, _step(*([source] if source else [])))
        _set_revision(self.engine, self.head)

    def stamp(self, cfg, target) -> None:
        self.calls.append(f"stamp {target}")
        _set_revision(self.engine, self.head)


def _setup_fresh(engine) -> None:
    pass


def _setup_utc_era(engine) -> None:
    Base.metadata.create_all(engine)
    _set_revision(engine, "20260801_0006")


def _setup_beijing_era(engine) -> None:
    Base.metadata.create_all(engine)
    _set_revision(engine, "20260928_0117")


def _setup_already_marked(engine) -> None:
    _setup_utc_era(engine)
    with Session(engine) as db:
        db.add(SystemConfig(key="time_storage", value="beijing_v1"))
        db.commit()


@pytest.mark.parametrize(
    ("setup", "expected_call", "expected_marker"),
    [
        (_setup_fresh, "upgrade head", "beijing_v1"),
        (_setup_utc_era, "upgrade head", "utc_pending"),
        (_setup_beijing_era, "upgrade head", "beijing_v1"),
        (_setup_already_marked, "upgrade head", "beijing_v1"),
    ],
)
def test_server_schema_records_where_the_data_came_from(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    setup,
    expected_call: str,
    expected_marker: str,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'server.sqlite'}")
    head = ScriptDirectory.from_config(migrate._alembic_config()).get_current_head()
    fake = _FakeAlembic(engine, head)
    monkeypatch.setattr(migrate, "command", fake)
    try:
        setup(engine)
        migrate._run_server_schema(engine)
        assert fake.calls == [expected_call]
        assert _marker(engine) == expected_marker
    finally:
        engine.dispose()


def test_server_schema_refuses_app_tables_without_alembic_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'server.sqlite'}")
    fake = _FakeAlembic(engine, "unused")
    monkeypatch.setattr(migrate, "command", fake)
    try:
        # Pre-Alembic install or another app's table in a shared schema: nothing may be altered.
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, login VARCHAR(32))")
        with pytest.raises(migrate.UnversionedSchemaError, match="alembic stamp 20260731_0001"):
            migrate._run_server_schema(engine)

        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE users")
        SystemConfig.__table__.create(engine)
        with pytest.raises(migrate.UnversionedSchemaError, match="leftover tables: system_configs"):
            migrate._run_server_schema(engine)

        assert fake.calls == []
        assert _marker(engine) is None
        assert set(sa.inspect(engine).get_table_names()) == {"system_configs"}
    finally:
        engine.dispose()


@pytest.fixture
def config_engine():
    engine = create_engine("sqlite:///:memory:")
    SystemConfig.__table__.create(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_hook_marks_only_upgrades_that_start_in_the_utc_era(config_engine) -> None:
    with config_engine.begin() as conn:
        hook = btm.UtcEraUpgradeMarker()
        _apply(hook, conn, _step("20260801_0005"))
        _apply(hook, conn, _step("20260801_0006"))
    assert _marker(config_engine) == "utc_pending"


@pytest.mark.parametrize(
    "steps",
    [
        # empty database: base -> 0001 -> ... passes through UTC-era revisions but is new
        [_step(), _step("20260731_0001"), _step("20260801_0006")],
        [_step("20260928_0117"), _step("20261010_0119")],
        [_step("20260801_0006", is_stamp=True)],
    ],
    ids=["chain-from-base", "post-switch", "stamp"],
)
def test_hook_leaves_other_runs_unmarked(config_engine, steps) -> None:
    with config_engine.begin() as conn:
        hook = btm.UtcEraUpgradeMarker()
        for step in steps:
            _apply(hook, conn, step)
    assert _marker(config_engine) is None


def test_hook_keeps_an_existing_marker(config_engine) -> None:
    with Session(config_engine) as db:
        db.add(SystemConfig(key="time_storage", value="beijing_v1"))
        db.commit()
    with config_engine.begin() as conn:
        _apply(btm.UtcEraUpgradeMarker(), conn, _step("20260801_0006"))
    assert _marker(config_engine) == "beijing_v1"


@pytest.mark.parametrize(
    ("marker", "revision", "expect_shift"),
    [
        ("utc_pending", "20261010_0119", True),
        (None, None, True),
        (None, "20260801_0006", True),
        (None, "20260928_0117", False),
        ("beijing_v1", None, False),
    ],
)
def test_server_shift_decision(
    config_engine,
    monkeypatch: pytest.MonkeyPatch,
    marker: str | None,
    revision: str | None,
    expect_shift: bool,
) -> None:
    mysql_like = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
    shifts: list[object] = []
    monkeypatch.setattr(btm, "current_revision", lambda _engine: revision)
    monkeypatch.setattr(btm, "_shift_to_beijing", lambda db, eng: shifts.append(eng))
    with Session(config_engine) as db:
        if marker is not None:
            db.add(SystemConfig(key="time_storage", value=marker))
            db.commit()
        btm.ensure_beijing_time_storage(db, mysql_like)
        assert db.get(SystemConfig, "time_storage").value == "beijing_v1"
    assert shifts == ([mysql_like] if expect_shift else [])


def test_failed_shift_leaves_the_marker_pending(
    config_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    mysql_like = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))

    def _boom(db, eng) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(btm, "_shift_to_beijing", _boom)
    with Session(config_engine) as db:
        db.add(SystemConfig(key="time_storage", value="utc_pending"))
        db.commit()
        with pytest.raises(RuntimeError):
            btm.ensure_beijing_time_storage(db, mysql_like)
        db.rollback()
        assert db.get(SystemConfig, "time_storage").value == "utc_pending"


def test_utc_era_revisions_end_at_the_beijing_switch() -> None:
    script = ScriptDirectory.from_config(migrate._alembic_config())
    chain = [rev.revision for rev in script.walk_revisions("base", "20260801_0006")]
    assert set(chain) == btm.UTC_ERA_REVISIONS
