"""安装向导：未选库时 status 不连库；SQLite create_all 后能建管理员。"""

from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, configure_engine
from app.core.file_config import write_json
from app.core.security import verify_password
from app.models.user import UserRole
from app.services.setup import complete_initial_admin, needs_setup


def test_setup_status_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    from app.api.setup import get_setup_status

    status = get_setup_status()
    assert status.needs_setup is True
    assert status.needs_database is True
    assert status.needs_admin is True
    assert "sqlite" in status.engines
    assert "mysql" in status.engines


def test_sqlite_create_all_then_admin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import database as dbmod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "zhange.sqlite"
    write_json("database", {"engine": "sqlite", "path": str(db_path)})
    get_settings.cache_clear()
    engine = configure_engine()
    from app.core.migrate import run_migrations

    run_migrations()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        assert needs_setup(db) is True
        monkeypatch.setattr(
            "app.services.setup.get_min_password_length", lambda _db: 8
        )
        monkeypatch.setattr(
            "app.services.setup.create_access_token", lambda _u, **_kw: "tok"
        )
        user, token = complete_initial_admin(
            db,
            email="admin@example.com",
            display_name="站长",
            password="Str0ng-Enough!",
        )
        assert token == "tok"
        assert user.role == UserRole.admin
        assert verify_password("Str0ng-Enough!", user.password_hash)
        assert needs_setup(db) is False
        assert "users" in Base.metadata.tables
    finally:
        db.close()
        engine.dispose()
        dbmod._engine = None
        dbmod._SessionLocal = None
        get_settings.cache_clear()
