"""ROR2 guide cache migrations add normalized Weblate state without altering Wiki raws."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.migrate import _alembic_config

_BEFORE = "20261020_0127"
_REVISION = "20261022_0129"


@pytest.fixture
def pre_translation_cache_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{tmp_path / 'zhange.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE guide_raws ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, game VARCHAR(32) NOT NULL, "
            "resource VARCHAR(64) NOT NULL, source VARCHAR(512) NOT NULL, "
            "raw_body TEXT NOT NULL, synced_at DATETIME NOT NULL, note TEXT, "
            "CONSTRAINT uq_guide_raws_game_resource UNIQUE (game, resource))"
        )
        connection.exec_driver_sql(
            "INSERT INTO guide_raws "
            "(game, resource, source, raw_body, synced_at, note) "
            "VALUES ('ror2', 'items', 'wiki', 'raw wiki body', '2026-10-22 00:00:00', NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES (?)", (_BEFORE,)
        )
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_upgrade_adds_weblate_cache_and_raw_fingerprint(pre_translation_cache_db) -> None:
    config = _alembic_config()
    command.upgrade(config, "head")

    inspector = sa.inspect(pre_translation_cache_db)
    tables = set(inspector.get_table_names())
    assert {"guide_raws", "guide_token_translations", "guide_token_translation_syncs"} <= tables
    raw_columns = {column["name"] for column in inspector.get_columns("guide_raws")}
    assert "content_fingerprint" in raw_columns
    assert inspector.get_unique_constraints("guide_token_translations") == [
        {
            "name": "uq_guide_token_translations_context",
            "column_names": ["game", "target_language", "context_hash"],
        }
    ]
    assert {
        "id",
        "game",
        "target_language",
        "context_hash",
        "context",
        "source_text",
        "source_fingerprint",
        "target_text",
        "translation_state",
    } == {column["name"] for column in inspector.get_columns("guide_token_translations")}
    assert {
        "game",
        "target_language",
        "scope_fingerprint",
        "source_manifest_fingerprint",
        "snapshot_fingerprint",
        "unit_count",
        "synced_at",
    } == {column["name"] for column in inspector.get_columns("guide_token_translation_syncs")}
    with pre_translation_cache_db.connect() as connection:
        raw = connection.exec_driver_sql(
            "SELECT raw_body, content_fingerprint FROM guide_raws WHERE game = 'ror2'"
        ).one()
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    assert raw.raw_body == "raw wiki body"
    assert raw.content_fingerprint is None  # Existing content is hashed lazily on next Wiki sync.
    assert revision == _REVISION

    # A second run at head is a no-op and does not modify the cached Wiki document.
    command.upgrade(config, "head")
    with pre_translation_cache_db.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT raw_body FROM guide_raws WHERE game = 'ror2'"
        ).scalar_one() == "raw wiki body"