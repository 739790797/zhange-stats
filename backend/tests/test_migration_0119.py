"""Migration 0119: SQLite orphan cleanup and the legacy repairs that used to run on every boot."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base
from app.core.migrate import _alembic_config
from app.models.articles import Article
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.minecraft import MinecraftServerProfile
from app.models.play_session import PlaySession
from app.models.system_config import SystemConfig
from app.models.tarkov import TarkovRaidRoom
from app.models.user import User

_NOW = datetime(2026, 10, 10, 12, 0)
_BEFORE = "20261010_0118"
_REVISION = "20261010_0119"


@pytest.fixture
def plain_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Foreign keys off, like a SQLite file the app wrote before it enforced them."""
    url = f"sqlite:///{tmp_path / 'zhange.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


def _upgrade_from_0118() -> None:
    cfg = _alembic_config()
    command.stamp(cfg, _BEFORE)
    command.upgrade(cfg, _REVISION)


def _session(member_id: int) -> PlaySession:
    return PlaySession(
        member_id=member_id,
        steam_app_id="730",
        game_name="CS2",
        started_at=_NOW,
        last_seen_at=_NOW,
    )


def test_orphans_follow_their_on_delete_action(plain_engine) -> None:
    with Session(plain_engine) as db:
        db.add(User(id=1, username="u1", display_name="U1", password_hash="x"))
        db.add(Member(id=1, nickname="kept", user_id=1))
        # user 99 is gone: the member cascades, then its sessions on the next pass
        db.add(Member(id=2, nickname="orphan", user_id=99))
        db.add_all([_session(1), _session(2), _session(42)])
        db.add(
            CheckinRolePref(platform="skland", member_id=77, game_code="arknights", role_uid="1")
        )
        db.add(TarkovRaidRoom(id=1, public_id="R1", host_user_id=55))
        db.add(Article(slug="a", title="A", author_user_id=88))
        db.commit()

    _upgrade_from_0118()

    with plain_engine.connect() as conn:
        assert conn.execute(select(Member.id)).scalars().all() == [1]
        assert conn.execute(select(PlaySession.member_id)).scalars().all() == [1]
        assert conn.execute(select(CheckinRolePref.id)).scalars().all() == []
        assert conn.execute(select(TarkovRaidRoom.host_user_id)).scalars().all() == [None]
        assert conn.execute(select(Article.author_user_id)).scalars().all() == [None]
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []

    # MariaDB DDL is not transactional; a re-run after a half-applied upgrade must be harmless.
    _upgrade_from_0118()
    with plain_engine.connect() as conn:
        assert conn.execute(select(Member.id)).scalars().all() == [1]


def test_legacy_register_challenges_rows_are_copied_not_dropped(plain_engine) -> None:
    with plain_engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE register_challenges")
        conn.exec_driver_sql(
            "CREATE TABLE register_challenges ("
            "email VARCHAR(128) NOT NULL PRIMARY KEY, "
            "code VARCHAR(16) NOT NULL, "
            "expires_at DATETIME NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO register_challenges (email, code, expires_at) "
            "VALUES ('a@example.com', '123456', '2026-10-10 12:00:00.000000')"
        )

    _upgrade_from_0118()

    insp = sa.inspect(plain_engine)
    assert set(insp.get_pk_constraint("register_challenges")["constrained_columns"]) == {
        "email",
        "purpose",
    }
    assert "ix_register_challenges_expires_at" in {
        ix["name"] for ix in insp.get_indexes("register_challenges")
    }
    with plain_engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT email, purpose, code, attempts FROM register_challenges"
        ).fetchall()
    assert [tuple(r) for r in rows] == [("a@example.com", "register", "123456", 0)]


def test_interrupted_register_challenges_rebuild_is_finished(plain_engine) -> None:
    with plain_engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE register_challenges")
        conn.exec_driver_sql(
            "CREATE TABLE _register_challenges_rebuild ("
            "email VARCHAR(128) NOT NULL, purpose VARCHAR(16) NOT NULL, "
            "code VARCHAR(16) NOT NULL, expires_at DATETIME NOT NULL, "
            "attempts INTEGER DEFAULT '0' NOT NULL, PRIMARY KEY (email, purpose))"
        )
        conn.exec_driver_sql(
            "INSERT INTO _register_challenges_rebuild VALUES "
            "('a@example.com', 'reset', '654321', '2026-10-10 12:00:00.000000', 2)"
        )

    _upgrade_from_0118()

    insp = sa.inspect(plain_engine)
    tables = set(insp.get_table_names())
    assert "register_challenges" in tables
    assert "_register_challenges_rebuild" not in tables
    assert "ix_register_challenges_expires_at" in {
        ix["name"] for ix in insp.get_indexes("register_challenges")
    }
    with plain_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT email, purpose, attempts FROM register_challenges")
        assert [tuple(r) for r in rows] == [("a@example.com", "reset", 2)]


def test_minecraft_public_address_moves_into_integrations(plain_engine) -> None:
    with Session(plain_engine) as db:
        db.add(MinecraftServerProfile(id=1, mc_version="1.20.1"))
        db.add(SystemConfig(key="integrations", value=json.dumps({"github_token": "t"})))
        db.commit()
    with plain_engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE minecraft_server_profiles ADD COLUMN public_host VARCHAR(255)"
        )
        conn.exec_driver_sql("ALTER TABLE minecraft_server_profiles ADD COLUMN public_port INTEGER")
        conn.exec_driver_sql(
            "UPDATE minecraft_server_profiles SET public_host = ' mc.example.com ', "
            "public_port = 25566 WHERE id = 1"
        )

    _upgrade_from_0118()

    cols = {c["name"] for c in sa.inspect(plain_engine).get_columns("minecraft_server_profiles")}
    assert not cols & {"public_host", "public_port"}
    with Session(plain_engine) as db:
        assert db.get(MinecraftServerProfile, 1).mc_version == "1.20.1"
        stored = json.loads(db.get(SystemConfig, "integrations").value)
    assert stored == {
        "github_token": "t",
        "minecraft_public_host": "mc.example.com",
        "minecraft_public_port": 25566,
    }


def test_create_all_era_arknights_indexes_are_added(plain_engine) -> None:
    with plain_engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX ix_arknights_operators_profession")
        conn.exec_driver_sql("DROP INDEX ix_arknights_operators_rarity")

    _upgrade_from_0118()

    names = {ix["name"] for ix in sa.inspect(plain_engine).get_indexes("arknights_operators")}
    assert {"ix_arknights_operators_profession", "ix_arknights_operators_rarity"} <= names
