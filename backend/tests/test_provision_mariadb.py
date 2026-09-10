"""MariaDB provisioner: URL / config/database.json helpers (no real server, no download)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "common" / "provision_mariadb.py"


def _load():
    spec = importlib.util.spec_from_file_location("provision_mariadb", _SCRIPTS)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_placeholder_and_loopback() -> None:
    m = _load()
    example = "mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats_dev"
    assert m.is_placeholder_url(example) is True
    assert m.is_placeholder_url("") is True
    assert m.is_placeholder_url("mysql+pymysql://zhange:secret@127.0.0.1:3306/zhange_stats") is False
    assert m.is_placeholder_url("mysql+pymysql://root:password@db.example.com:3306/zhange") is False
    assert m.is_loopback_host("127.0.0.1") is True
    assert m.is_loopback_host("localhost") is True
    assert m.is_loopback_host("::1") is True
    assert m.is_loopback_host("db.internal") is False


def test_parse_and_build_url_roundtrip() -> None:
    m = _load()
    url = m.build_database_url("zhange", "p@ss/w:rd", "127.0.0.1", 3307, "zhange_stats_dev")
    parsed = m.parse_database_url(url)
    assert parsed.user == "zhange"
    assert parsed.password == "p@ss/w:rd"
    assert parsed.host == "127.0.0.1"
    assert parsed.port == 3307
    assert parsed.database == "zhange_stats_dev"
    assert "p%40ss" in url


def test_write_database_url_creates_config(tmp_path: Path) -> None:
    m = _load()
    url = "mysql+pymysql://zhange:x@127.0.0.1:3306/zhange_stats"
    m.write_database_url(tmp_path, url)
    data = json.loads((tmp_path / "config" / "database.json").read_text(encoding="utf-8"))
    assert data["engine"] == "mysql"
    assert data["url"] == url
    assert data["_version"] == 1


def test_write_database_url_keeps_extra_keys(tmp_path: Path) -> None:
    m = _load()
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "database.json").write_text(
        json.dumps({"_version": 1, "engine": "sqlite", "path": "data/runtime/zhange.sqlite"}),
        encoding="utf-8",
    )
    m.write_database_url(tmp_path, "mysql+pymysql://zhange:x@127.0.0.1:3306/db")
    data = json.loads((cfg / "database.json").read_text(encoding="utf-8"))
    assert data["engine"] == "mysql"
    assert data["path"] == "data/runtime/zhange.sqlite"
    assert data["_version"] == 1


def test_read_configured_database_url_prefers_process_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _load()
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://from-env@127.0.0.1:3306/e")
    m.write_database_url(tmp_path, "mysql+pymysql://from-file@127.0.0.1:3306/f")
    assert "from-env@" in m.read_configured_database_url(tmp_path)


def test_read_configured_database_url_falls_back_to_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _load()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=mysql+pymysql://legacy@127.0.0.1:3306/old\n",
        encoding="utf-8",
    )
    assert "legacy@" in m.read_configured_database_url(tmp_path)


def test_choose_database_name() -> None:
    m = _load()
    parsed = m.parse_database_url("mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats_dev")
    assert m.choose_database_name({"APP_ENV": "development"}, parsed, placeholder=True) == "zhange_stats_dev"
    assert m.choose_database_name({"APP_ENV": "production"}, parsed, placeholder=True) == "zhange_stats_dev"
    empty = m.parse_database_url("mysql+pymysql://root:password@127.0.0.1:3306/")
    assert m.choose_database_name({}, empty, placeholder=True) == "zhange_stats"
    custom = m.parse_database_url("mysql+pymysql://u:p@127.0.0.1:3306/mine")
    assert m.choose_database_name({"APP_ENV": "production"}, custom, placeholder=False) == "mine"


def test_skip_env(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _load()
    monkeypatch.delenv("ZHANGE_SKIP_MARIADB", raising=False)
    assert m.should_skip() is False
    monkeypatch.setenv("ZHANGE_SKIP_MARIADB", "1")
    assert m.should_skip() is True


def test_sql_ident_rejects_injection() -> None:
    m = _load()
    assert m.sql_ident("zhange_stats_dev") == "`zhange_stats_dev`"
    with pytest.raises(m.ProvisionError):
        m.sql_ident("zhange`; DROP TABLE users;--")


def test_safe_extract_zip_rejects_parent(tmp_path: Path) -> None:
    m = _load()
    import io
    import zipfile

    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as zf:
        zf.writestr("../escape.txt", "nope")
    archive = tmp_path / "bad.zip"
    archive.write_bytes(blob.getvalue())
    with pytest.raises(m.ProvisionError):
        m.safe_extract_zip(archive, tmp_path / "out")


def test_portable_layout_uses_data_mariadb(tmp_path: Path) -> None:
    m = _load()
    paths = m.portable_layout(tmp_path)
    assert paths["base"] == tmp_path / "data" / "mariadb"
    assert paths["provision"] == tmp_path / "data" / "mariadb" / "provision.json"


def test_portable_layout_relocates_legacy_var(tmp_path: Path) -> None:
    m = _load()
    old = tmp_path / "var" / "mariadb"
    old.mkdir(parents=True)
    (old / "my.ini").write_text("[mysqld]\n", encoding="utf-8")
    paths = m.portable_layout(tmp_path)
    assert paths["base"] == tmp_path / "data" / "mariadb"
    assert (tmp_path / "data" / "mariadb" / "my.ini").is_file()
    assert not old.exists()
