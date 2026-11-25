"""Upgrade an existing SQLite install and keep its retired raw data."""

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base
from app.core.migrate import _alembic_config
from app.core.timeutil import now_naive
from app.models.arknights_rogue import ArknightsRogueRaw
from app.models.member import Member
from app.models.skland import SklandBind

_PREVIOUS = "20261022_0129"
_STRONGHOLD = "20261124_0130"
_RECORDS = "20261124_0131"
_SITE_DIARY = "20261124_0132"


def test_sqlite_stronghold_upgrade_downgrade_preserve_legacy_rows(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'stronghold.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = sa.create_engine(url)
    try:
        previous_tables = [
            table for table in Base.metadata.sorted_tables if not table.name.startswith("arknights_stronghold_")
        ]
        Base.metadata.create_all(engine, tables=previous_tables)
        with Session(engine) as db:
            db.add(Member(id=1, nickname="历史角色"))
            db.flush()
            db.add(SklandBind(id=1, member_id=1, token_enc="fixture"))
            db.add(ArknightsRogueRaw(member_id=1, uid="12345", topic_id="retired", raw_json="{}"))
            db.commit()
        cfg = _alembic_config()
        command.stamp(cfg, _PREVIOUS)
        command.upgrade(cfg, _STRONGHOLD)
        with engine.begin() as conn:
            metadata = sa.MetaData()
            roles = sa.Table("arknights_stronghold_roles", metadata, autoload_with=conn)
            matches = sa.Table("arknights_stronghold_matches", metadata, autoload_with=conn)
            views = sa.Table("arknights_stronghold_views", metadata, autoload_with=conn)
            dt = now_naive()
            match_id = "f" * 32
            conn.execute(
                roles.insert().values(id=1, bind_id=1, channel_id="1", uid="12345", role_name="旧角色", synced_at=dt)
            )
            conn.execute(
                matches.insert().values(
                    id=match_id,
                    source_key="f" * 64,
                    season_id="season",
                    season_label="历史赛季",
                    difficulty_id="hard",
                    difficulty_label="进阶模拟",
                    ended_at=dt,
                    success=True,
                )
            )
            conn.execute(views.insert().values(match_id=match_id, role_id=1, shared=True))
        command.upgrade(cfg, _RECORDS)
        command.upgrade(cfg, _RECORDS)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            assert ctx.get_current_revision() == _RECORDS
            assert conn.execute(sa.select(ArknightsRogueRaw.uid)).scalar_one() == "12345"
            record = conn.execute(
                sa.text("SELECT match_id, role_id, complete_state, bonds_known FROM arknights_stronghold_records")
            ).one()
            assert tuple(record) == (match_id, 1, None, 0)
            assert conn.execute(sa.select(views.c.shared)).scalar_one() is True
        command.downgrade(cfg, _STRONGHOLD)
        with engine.connect() as conn:
            assert conn.execute(sa.select(views.c.shared)).scalar_one() is True
        command.upgrade(cfg, _RECORDS)
        command.downgrade(cfg, _PREVIOUS)
        assert set(sa.inspect(engine).get_table_names()) == {table.name for table in previous_tables} | {
            "alembic_version"
        }
        with engine.connect() as conn:
            assert conn.execute(sa.select(ArknightsRogueRaw.uid)).scalar_one() == "12345"
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "dialect", ["sqlite", "mariadb"] if os.getenv("ZHANGE_TEST_STRONGHOLD_MIGRATION_MYSQL_URL") else ["sqlite"]
)
@pytest.mark.parametrize("interrupted", [False, True])
def test_diary_upgrade_keeps_pending_records_and_survives_unbind(tmp_path, monkeypatch, dialect, interrupted):
    url = (
        os.environ["ZHANGE_TEST_STRONGHOLD_MIGRATION_MYSQL_URL"]
        if dialect == "mariadb"
        else f"sqlite:///{tmp_path / 'stronghold-site.sqlite'}"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    from app.core.database import _build_engine

    engine = _build_engine(url)
    previous_tables = [t for t in Base.metadata.sorted_tables if not t.name.startswith("arknights_stronghold_")]
    cfg = _alembic_config()
    dt = now_naive()
    legacy_report = "f" * 32
    single_id = "1" * 32
    pending_id = "2" * 32
    try:
        Base.metadata.create_all(engine, tables=previous_tables)
        command.stamp(cfg, _PREVIOUS)
        command.upgrade(cfg, _RECORDS)
        with engine.begin() as conn:
            meta = sa.MetaData()
            names = ("roles", "matches", "views", "records", "view_bonds")
            roles, matches, views, records, bonds = [
                sa.Table(f"arknights_stronghold_{t}", meta, autoload_with=conn, resolve_fks=False) for t in names
            ]
            conn.execute(Member.__table__.insert().values(id=1, nickname="历史角色"))
            conn.execute(SklandBind.__table__.insert().values(id=1, member_id=1, token_enc="fixture"))
            conn.execute(
                roles.insert().values(id=1, bind_id=1, channel_id="1", uid="12345", role_name="样本", synced_at=dt)
            )
            scope = dict(
                season_id="s1", season_label="赛季", difficulty_id="abyss", difficulty_label="终极模拟", ended_at=dt
            )
            conn.execute(
                matches.insert().values(
                    id=legacy_report, source_key="f" * 64, success=False, mode_type="single", **scope
                )
            )
            conn.execute(views.insert().values(match_id=legacy_report, role_id=1, shared=False))
            for record_id, mode, match_id in ((single_id, "single", legacy_report), (pending_id, "multi", None)):
                conn.execute(
                    records.insert().values(
                        id=record_id,
                        role_id=1,
                        match_id=match_id,
                        source_view_key=record_id * 2,
                        mode_type=mode,
                        complete_state=True,
                        pass_round=15,
                        bonds_known=True,
                        **scope,
                    )
                )
                conn.execute(
                    bonds.insert().values(
                        view_id=record_id,
                        bond_id="a",
                        name="坚守",
                        active=True,
                        layer=100,
                        layer_scope="unknown",
                    )
                )
        command.upgrade(cfg, _SITE_DIARY)
        if interrupted:
            create_index = Operations.create_index

            def interrupt_at_alias_index(self, name, *args, **kwargs):
                if name == "ix_arknights_stronghold_record_aliases_record_id":
                    raise RuntimeError("simulated interruption after DDL")
                return create_index(self, name, *args, **kwargs)

            with monkeypatch.context() as patch:
                patch.setattr(Operations, "create_index", interrupt_at_alias_index)
                with pytest.raises(RuntimeError, match="simulated interruption after DDL"):
                    command.upgrade(cfg, "20261124_0133")
            with engine.connect() as conn:
                assert MigrationContext.configure(conn).get_current_revision() == _SITE_DIARY
                names = {i["name"] for i in sa.inspect(conn).get_indexes("arknights_stronghold_record_aliases")}
                assert "ix_arknights_stronghold_record_aliases_record_id" not in names
        command.upgrade(cfg, "20261124_0133")
        command.upgrade(cfg, "20261124_0133")
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            assert ctx.get_current_revision() == "20261124_0133"
            assert compare_metadata(ctx, Base.metadata) == []
            assert conn.execute(sa.text("SELECT member_id FROM arknights_stronghold_roles")).scalar_one() == 1
            assert conn.execute(sa.text("SELECT COUNT(*) FROM arknights_stronghold_matches")).scalar_one() == 2
            assert not sa.inspect(conn).has_table("arknights_stronghold_views")
            assert (
                conn.execute(
                    sa.text("SELECT match_id FROM arknights_stronghold_records WHERE id=:id"), {"id": single_id}
                ).scalar_one()
                == legacy_report
            )
            pending = conn.execute(
                sa.text(
                    "SELECT m.identity_kind FROM arknights_stronghold_records r "
                    "JOIN arknights_stronghold_matches m ON m.id = r.match_id WHERE r.id=:id"
                ),
                {"id": pending_id},
            ).scalar_one()
            assert pending == "record"
            assert (
                conn.execute(
                    sa.text("SELECT COUNT(*) FROM arknights_stronghold_matches WHERE scene_key IS NULL")
                ).scalar_one()
                == 2
            )
            assert sa.inspect(conn).has_table("arknights_stronghold_versions")
            conn.execute(SklandBind.__table__.delete().where(SklandBind.id == 1))
            assert conn.execute(sa.text("SELECT COUNT(*) FROM arknights_stronghold_records")).scalar_one() == 2
            assert conn.execute(sa.text("SELECT COUNT(*) FROM arknights_stronghold_view_bonds")).scalar_one() == 2
            if dialect == "sqlite":
                assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        if dialect == "mariadb":
            Base.metadata.drop_all(engine)
            with engine.begin() as conn:
                conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        engine.dispose()
        get_settings.cache_clear()
