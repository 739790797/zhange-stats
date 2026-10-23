from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command

from app.core.config import get_settings
from app.core.migrate import _alembic_config
from app.models.job_run import JobRun
from app.models.job_run_log import JobRunLog


def test_job_run_log_migration_and_model_match_on_sqlite(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "migration.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    cfg = _alembic_config()
    engine = sa.create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        JobRun.__table__.create(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO alembic_version (version_num) VALUES (?)",
                ("20261015_0126",),
            )

        command.upgrade(cfg, "head")

        inspector = sa.inspect(engine)
        assert "job_run_logs" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("job_run_logs")} == set(
            JobRunLog.__table__.columns.keys()
        )
        assert {index["name"] for index in inspector.get_indexes("job_run_logs")} >= {
            "ix_job_run_logs_run_id_id"
        }
        foreign_keys = inspector.get_foreign_keys("job_run_logs")
        assert any(
            foreign_key["referred_table"] == "job_runs"
            and foreign_key["options"].get("ondelete") == "CASCADE"
            for foreign_key in foreign_keys
        )

        command.downgrade(cfg, "20261015_0126")
        assert "job_run_logs" not in sa.inspect(engine).get_table_names()
        command.upgrade(cfg, "head")
        assert "job_run_logs" in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()
        get_settings.cache_clear()
