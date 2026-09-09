"""MariaDB provisioner: URL / .env helpers (no real server, no download)."""

from __future__ import annotations

import importlib.util
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


def test_set_env_value_replaces_and_preserves(tmp_path: Path) -> None:
    m = _load()
    env = tmp_path / ".env"
    env.write_text(
        "# comment\nDATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/zhange_stats_dev\nREDIS_URL=\n",
        encoding="utf-8",
    )
    m.set_env_value(env, "DATABASE_URL", "mysql+pymysql://zhange:x@127.0.0.1:3306/zhange_stats")
    text = env.read_text(encoding="utf-8")
    assert text.count("DATABASE_URL=") == 1
    assert "zhange:x@" in text
    assert "REDIS_URL=" in text
    assert text.startswith("# comment")


def test_set_env_value_appends_missing_key(tmp_path: Path) -> None:
    m = _load()
    env = tmp_path / ".env"
    env.write_text("APP_ENV=development\n", encoding="utf-8")
    m.set_env_value(env, "DATABASE_URL", "mysql+pymysql://zhange:x@127.0.0.1:3306/db")
    text = env.read_text(encoding="utf-8")
    assert "APP_ENV=development" in text
    assert text.strip().endswith("DATABASE_URL=mysql+pymysql://zhange:x@127.0.0.1:3306/db")


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
