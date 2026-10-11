"""HTTP 首次安装向导：未选库 → SQLite → 管理员；不碰真实安装根。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core import database as dbmod
from app.services.setup import (
    SETUP_TOKEN_HEADER,
    read_setup_token,
    reset_setup_complete_for_tests,
)

_SECRET_MYSQL_URL = "mysql+pymysql://zhange_user:s3cret-pw@db.internal:3306/zhange"
_SECRET_PARTS = ("s3cret-pw", "zhange_user", "db.internal")


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


def _sqlite_tables(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def _mysql_url_opens_standin(monkeypatch: pytest.MonkeyPatch, standin: Path) -> None:
    """MySQL 连接串改连本地 SQLite 替身，替身按服务器库的规则建表/迁移。"""
    from app.core import file_config, migrate

    real_configure = dbmod.configure_engine
    real_sqlite_schema = migrate._run_sqlite_schema
    monkeypatch.setattr(file_config, "ping_mysql_url", lambda _url, **_kw: None)
    monkeypatch.setattr(
        "app.api.setup.configure_engine",
        lambda url=None: real_configure(
            f"sqlite:///{standin.as_posix()}" if url and url.startswith("mysql") else url
        ),
    )

    def schema(engine) -> None:
        if engine.url.database == standin.as_posix():
            migrate._run_server_schema(engine)
        else:
            real_sqlite_schema(engine)

    monkeypatch.setattr(migrate, "_run_sqlite_schema", schema)


def test_unversioned_database_refused_and_choice_rolled_back(
    fresh_install: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """有 users 无 alembic_version 的库：409 给修复说明，database.json 恢复原样，向导还能换库。"""
    from app.core.file_config import config_path
    from app.core.migrate import _PRE_ALEMBIC_HELP
    from app.main import app

    standin = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(standin)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    _mysql_url_opens_standin(monkeypatch, standin)
    db_json = config_path("database")
    original = b'{\n  "_version": 1\n}\n'
    db_json.write_bytes(original)

    with TestClient(app) as client:
        auth = {SETUP_TOKEN_HEADER: read_setup_token()}
        refused = client.post(
            "/api/setup/database",
            json={"engine": "mysql", "url": _SECRET_MYSQL_URL},
            headers=auth,
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == _PRE_ALEMBIC_HELP
        assert not any(part in refused.text for part in _SECRET_PARTS)
        assert db_json.read_bytes() == original
        assert _sqlite_tables(standin) == {"users"}
        assert client.get("/api/setup/status").json()["needs_database"] is True

        retry = client.post("/api/setup/database", json={"engine": "sqlite"}, headers=auth)
        assert retry.status_code == 200, retry.text
        assert client.get("/api/setup/status").json()["needs_database"] is False


def test_schema_failure_rolls_back_without_leaking_credentials(
    fresh_install: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.core import file_config
    from app.core.file_config import config_path
    from app.main import app

    monkeypatch.setattr(file_config, "ping_mysql_url", lambda _url, **_kw: None)
    monkeypatch.setattr("app.api.setup.configure_engine", lambda url=None: None)

    def fail() -> None:
        raise RuntimeError(f"(1142, 'CREATE command denied') while using {_SECRET_MYSQL_URL}")

    monkeypatch.setattr("app.api.setup._apply_schema", fail)
    with TestClient(app) as client, caplog.at_level("ERROR", logger="zhange.setup"):
        failed = client.post(
            "/api/setup/database",
            json={"engine": "mysql", "url": _SECRET_MYSQL_URL},
            headers={SETUP_TOKEN_HEADER: read_setup_token()},
        )
        assert failed.status_code == 500
        assert failed.json()["detail"] == "建表或迁移失败，已撤回这次数据库选择；详情见服务日志"
        assert not any(part in failed.text for part in _SECRET_PARTS)
        assert not config_path("database").exists()
        assert client.get("/api/setup/status").json()["needs_database"] is True
    logged = [r.getMessage() for r in caplog.records if r.name == "zhange.setup"]
    assert any("rolled back" in m and "CREATE command denied" in m for m in logged)
    assert not any("s3cret-pw" in m or "zhange_user" in m for m in logged)


def test_first_deploy_sqlite_wizard_http(
    fresh_install: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    startup_calls: list[str] = []
    monkeypatch.setattr(
        "app.api.setup.run_post_database_startup",
        lambda _scheduler, **_kw: startup_calls.append("post_db"),
    )
    monkeypatch.setattr(
        "app.api.setup.start_background_services",
        lambda: startup_calls.append("background"),
    )
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
        assert data["token_required"] is True
        install_token = read_setup_token()
        assert install_token
        assert install_token not in status.text
        auth = {SETUP_TOKEN_HEADER: install_token}

        no_token = client.post("/api/setup/database", json={"engine": "sqlite"})
        assert no_token.status_code == 403
        wrong_token = client.post(
            "/api/setup/database",
            json={"engine": "sqlite"},
            headers={SETUP_TOKEN_HEADER: install_token + "x"},
        )
        assert wrong_token.status_code == 403
        assert not sqlite_file.exists()

        bad_mysql = client.post(
            "/api/setup/database",
            json={"engine": "mysql", "url": "mysql+pymysql://u:s3cret@127.0.0.1:1/nope"},
            headers=auth,
        )
        assert bad_mysql.status_code == 400
        # 驱动原文（主机、端口、账号）只进服务端日志，不回给浏览器
        assert bad_mysql.json()["detail"] == "无法连接数据库，请检查主机、端口、库名与账号密码"
        assert "127.0.0.1" not in bad_mysql.text
        assert "s3cret" not in bad_mysql.text
        assert client.get("/api/setup/status").json()["needs_database"] is True

        created = client.post("/api/setup/database", json={"engine": "sqlite"}, headers=auth)
        assert created.status_code == 200, created.text
        assert created.json()["engine"] == "sqlite"
        assert sqlite_file.is_file()

        after_db = client.get("/api/setup/status").json()
        assert after_db["needs_database"] is False
        assert after_db["needs_admin"] is True
        assert after_db["needs_setup"] is True
        assert after_db["token_required"] is True
        assert read_setup_token() == install_token

        again = client.post("/api/setup/database", json={"engine": "sqlite"}, headers=auth)
        assert again.status_code == 409

        admin_body = {
            "email": "admin@example.com",
            "display_name": "站长",
            "password": "Str0ng-Enough!",
        }
        assert client.post("/api/setup/admin", json=admin_body).status_code == 403

        weak = client.post(
            "/api/setup/admin",
            json={**admin_body, "password": "123456"},
            headers=auth,
        )
        assert weak.status_code == 400

        admin = client.post("/api/setup/admin", json=admin_body, headers=auth)
        assert admin.status_code == 200, admin.text
        assert admin.json() == {"message": "初始化完成，已创建管理员账号"}
        assert client.cookies.get("zhange_access")
        assert startup_calls == ["post_db", "background"]
        assert read_setup_token() == ""

        done = client.get("/api/setup/status").json()
        assert done["needs_setup"] is False
        assert done["needs_database"] is False
        assert done["needs_admin"] is False
        assert done["token_required"] is False
        assert read_setup_token() == ""

        second = client.post(
            "/api/setup/admin",
            json={**admin_body, "email": "late@example.com"},
            headers=auth,
        )
        assert second.status_code == 409

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "admin@example.com"
        assert me.json()["role"] == "admin"
