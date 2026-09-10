"""HTTP 首次安装向导：未选库 → SQLite → 管理员；不碰真实安装根。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core import database as dbmod
from app.services.setup import reset_setup_complete_for_tests


def _cleanup_engine() -> None:
    if dbmod._engine is not None:
        try:
            dbmod._engine.dispose()
        except Exception:  # noqa: BLE001
            pass
    dbmod._engine = None
    dbmod._SessionLocal = None
    get_settings.cache_clear()


@pytest.fixture
def fresh_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    install = tmp_path / "install"
    install.mkdir()
    monkeypatch.setenv("APP_INSTALL_DIR", str(install))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_setup_complete_for_tests()
    _cleanup_engine()
    yield install
    reset_setup_complete_for_tests()
    _cleanup_engine()


def test_first_deploy_sqlite_wizard_http(fresh_install: Path) -> None:
    from app.main import app

    sqlite_file = fresh_install / "data" / "runtime" / "zhange.sqlite"
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "setup"
        assert body["database"] == "unconfigured"

        blocked = client.get("/api/settings/runtime-env")
        assert blocked.status_code == 503
        assert blocked.json().get("code") == "SETUP_REQUIRED"

        status = client.get("/api/setup/status")
        assert status.status_code == 200
        data = status.json()
        assert data["needs_setup"] is True
        assert data["needs_database"] is True
        assert data["needs_admin"] is True
        assert data["engines"] == ["sqlite", "mysql"]
        assert "zhange.sqlite" in data["sqlite_path"]

        bad_mysql = client.post(
            "/api/setup/database",
            json={"engine": "mysql", "url": "mysql+pymysql://u:p@127.0.0.1:1/nope"},
        )
        assert bad_mysql.status_code == 400
        assert client.get("/api/setup/status").json()["needs_database"] is True

        created = client.post("/api/setup/database", json={"engine": "sqlite"})
        assert created.status_code == 200, created.text
        assert created.json()["engine"] == "sqlite"
        assert sqlite_file.is_file()

        after_db = client.get("/api/setup/status").json()
        assert after_db["needs_database"] is False
        assert after_db["needs_admin"] is True
        assert after_db["needs_setup"] is True

        again = client.post("/api/setup/database", json={"engine": "sqlite"})
        assert again.status_code == 409

        weak = client.post(
            "/api/setup/admin",
            json={
                "email": "admin@example.com",
                "display_name": "站长",
                "password": "123456",
            },
        )
        assert weak.status_code == 400

        admin = client.post(
            "/api/setup/admin",
            json={
                "email": "admin@example.com",
                "display_name": "站长",
                "password": "Str0ng-Enough!",
            },
        )
        assert admin.status_code == 200, admin.text
        assert admin.json()["access_token"]
        token = admin.json()["access_token"]
        assert client.cookies.get("zhange_access")

        done = client.get("/api/setup/status").json()
        assert done["needs_setup"] is False
        assert done["needs_database"] is False
        assert done["needs_admin"] is False

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == "admin@example.com"
        assert me.json()["role"] == "admin"
