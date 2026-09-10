"""Fill config/*.json from scripts/config.example without clobbering user values."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config_sync import fill_missing, sync_site_config
from app.core.file_config import read_json, write_json


def test_fill_missing_keeps_user_and_adds_keys() -> None:
    template = {
        "_version": 2,
        "APP_ENV": "development",
        "NEW_FLAG": False,
        "nested": {"a": 1, "b": 2},
    }
    current = {
        "_version": 1,
        "APP_ENV": "production",
        "nested": {"a": 9, "extra": True},
    }
    got = fill_missing(template, current)
    assert got["APP_ENV"] == "production"
    assert got["NEW_FLAG"] is False
    assert got["nested"]["a"] == 9
    assert got["nested"]["b"] == 2
    assert got["nested"]["extra"] is True
    assert got["_version"] == 2


def test_fill_missing_none_copies_template() -> None:
    template = {"_version": 1, "min_password_length": 8}
    got = fill_missing(template, None)
    assert got == template
    got["min_password_length"] = 10
    assert template["min_password_length"] == 8


def _example_install(tmp_path: Path) -> Path:
    install = tmp_path / "install"
    (install / "backend").mkdir(parents=True)
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    example = install / "scripts" / "config.example"
    example.mkdir(parents=True)
    (example / "auth.json").write_text(
        json.dumps({"_version": 2, "min_password_length": 8, "icp_beian_no": ""}),
        encoding="utf-8",
    )
    (example / "app.json").write_text(
        json.dumps({"_version": 1, "APP_ENV": "development", "REDIS_URL": ""}),
        encoding="utf-8",
    )
    (example / "database.json").write_text(
        json.dumps(
            {
                "_version": 1,
                "engine": "sqlite",
                "path": "data/runtime/zhange.sqlite",
                "url": "",
            }
        ),
        encoding="utf-8",
    )
    return install


def test_sync_creates_auth_not_database(tmp_path: Path) -> None:
    install = _example_install(tmp_path)
    assert read_json("database") is None
    written = sync_site_config(install=install)
    assert "auth" in written
    assert "database" not in written
    assert read_json("database") is None
    auth = read_json("auth")
    assert auth is not None
    assert auth["_version"] == 2
    assert auth["min_password_length"] == 8


def test_sync_upgrades_existing_file(tmp_path: Path) -> None:
    install = _example_install(tmp_path)
    write_json("auth", {"min_password_length": 12, "icp_beian_no": "浙ICP备1号"})
    written = sync_site_config(install=install)
    assert "auth" in written
    auth = read_json("auth")
    assert auth is not None
    assert auth["min_password_length"] == 12
    assert auth["icp_beian_no"] == "浙ICP备1号"
    assert auth["_version"] == 2


def test_fill_missing_keeps_user_lists() -> None:
    template = {"_version": 2, "engines": ["paddle", "easyocr"], "flag": True}
    current = {"_version": 1, "engines": ["paddle"]}
    got = fill_missing(template, current)
    assert got["engines"] == ["paddle"]
    assert got["flag"] is True
    assert got["_version"] == 2


def test_sync_fills_existing_database_keys(tmp_path: Path) -> None:
    install = _example_install(tmp_path)
    write_json("database", {"engine": "mysql", "url": "mysql+pymysql://u:p@127.0.0.1/db"})
    written = sync_site_config(install=install)
    assert "database" in written
    db = read_json("database")
    assert db is not None
    assert db["engine"] == "mysql"
    assert db["url"] == "mysql+pymysql://u:p@127.0.0.1/db"
    assert db["path"] == "data/runtime/zhange.sqlite"
    assert db["_version"] == 1


def test_sync_idempotent(tmp_path: Path) -> None:
    install = _example_install(tmp_path)
    first = sync_site_config(install=install)
    assert first
    second = sync_site_config(install=install)
    assert second == []


def test_write_json_keeps_version() -> None:
    write_json("auth", {"_version": 1, "icp_beian_no": "a"})
    write_json("auth", {"icp_beian_no": "b"})
    loaded = read_json("auth")
    assert loaded is not None
    assert loaded["icp_beian_no"] == "b"
    assert loaded["_version"] == 1


def test_repo_templates_have_version() -> None:
    from app.core.file_config import CONFIG_NAMES, config_schema_version

    root = Path(__file__).resolve().parents[2]
    example = root / "scripts" / "config.example"
    for name in CONFIG_NAMES:
        payload = json.loads((example / f"{name}.json").read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert config_schema_version(payload) >= 1
