"""config/*.json 读写与旧 .env 迁入。"""

from pathlib import Path

import pytest

from app.core.file_config import read_json, write_json
from app.services.config_import import import_legacy_dotenv


def test_write_read_roundtrip() -> None:
    write_json("auth", {"icp_beian_no": "浙ICP备1号", "min_password_length": 10})
    loaded = read_json("auth")
    assert loaded is not None
    assert loaded["icp_beian_no"] == "浙ICP备1号"
    assert loaded["min_password_length"] == 10


def test_missing_file_returns_none() -> None:
    assert read_json("email") is None


def test_import_legacy_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import file_config as fc
    from app.services import config_import as ci

    install = tmp_path / "install"
    install.mkdir()
    (install / ".env").write_text(
        "DATABASE_URL=mysql+pymysql://u:p@127.0.0.1:3306/zhange\n"
        "APP_ENV=production\n"
        "PUBLIC_BACKEND_URL=http://127.0.0.1:6130\n"
        "DATA_DIR=D:/Project/zhange-stats/var/data\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ci, "resolve_install_dir", lambda: install)
    fc.set_config_dir_for_tests(install / "config")
    import_legacy_dotenv()
    db = read_json("database")
    assert db is not None
    assert db["url"].startswith("mysql")
    app = read_json("app")
    assert app is not None
    assert app["APP_ENV"] == "production"
    assert app["PUBLIC_BACKEND_URL"] == "http://127.0.0.1:6130"
    assert app["DATA_DIR"].endswith("var/data")


def test_import_legacy_dotenv_does_not_overwrite() -> None:
    write_json("database", {"engine": "sqlite", "path": "var/data/zhange.sqlite"})
    write_json("app", {"APP_ENV": "development"})
    import_legacy_dotenv()
    assert read_json("database")["engine"] == "sqlite"


def test_sqlite_url_in_database_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.file_config import resolve_database_url

    monkeypatch.delenv("DATABASE_URL", raising=False)
    write_json("database", {"engine": "sqlite", "url": "sqlite:///C:/tmp/legacy.sqlite"})
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert resolve_database_url() == "sqlite:///C:/tmp/legacy.sqlite"


def test_save_database_settings_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import file_config as fc

    install = tmp_path / "install"
    install.mkdir()
    monkeypatch.setattr(fc, "resolve_install_dir", lambda: install)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = fc.save_database_settings(engine="sqlite", path="data/runtime/zhange.sqlite")
    assert out["db_engine"] == "sqlite"
    assert out["db_path"] == "data/runtime/zhange.sqlite"
    assert out["db_url"] == ""
    stored = fc.read_json("database")
    assert stored is not None
    assert stored["engine"] == "sqlite"
    assert stored["path"] == "data/runtime/zhange.sqlite"
    assert (install / "data" / "runtime").is_dir()


def test_save_database_settings_rejects_bad_engine() -> None:
    from app.core.file_config import DatabaseSettingsError, save_database_settings

    with pytest.raises(DatabaseSettingsError, match="sqlite 或 mysql"):
        save_database_settings(engine="postgres")


def test_save_database_settings_rejects_non_mysql_url() -> None:
    from app.core.file_config import DatabaseSettingsError, save_database_settings

    with pytest.raises(DatabaseSettingsError, match="mysql"):
        save_database_settings(engine="mysql", url="postgres://x")


def test_load_database_settings_defaults_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.file_config import load_database_settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = load_database_settings()
    assert out["db_engine"] == "sqlite"
    assert out["db_path"]



def test_import_legacy_system_configs() -> None:
    import json

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.crypto_secret import encrypt_secret
    from app.core.database import Base
    from app.models.system_config import SystemConfig
    from app.services.config_import import import_legacy_system_configs

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(
        SystemConfig(
            key="email_smtp",
            value=json.dumps(
                {
                    "smtp_host": "smtp.example.com",
                    "smtp_password": encrypt_secret("secret-pw"),
                }
            ),
        )
    )
    db.add(
        SystemConfig(
            key="integrations",
            value=json.dumps(
                {
                    "steam_api_key": encrypt_secret("S" * 32),
                    "pelican_base_url": "https://panel.example.com",
                    "pelican_server_uuid": "c903b918-4c4d-41cf-9827-9af061e431f0",
                    "minecraft_public_host": "zhange.space",
                }
            ),
        )
    )
    db.add(SystemConfig(key="site", value=json.dumps({"icp_beian_no": "测ICP备1号"})))
    db.add(
        SystemConfig(
            key="ocr",
            value=json.dumps({"paddle_profile": "v6_medium", "engines": {"paddle": True}}),
        )
    )
    db.add(
        SystemConfig(
            key="platform_features",
            value=json.dumps({"features": {"steam": True, "skland": False}}),
        )
    )
    db.commit()
    try:
        import_legacy_system_configs(db)
        email = read_json("email")
        assert email is not None
        assert email["smtp_host"] == "smtp.example.com"
        assert email["smtp_password"] == "secret-pw"
        integ = read_json("integrations")
        assert integ is not None
        assert integ["steam_api_key"] == "S" * 32
        assert integ["pelican_server_uuid"] == "c903b918-4c4d-41cf-9827-9af061e431f0"
        assert integ["minecraft_public_host"] == "zhange.space"
        assert read_json("auth")["icp_beian_no"] == "测ICP备1号"
        assert read_json("ocr")["paddle_profile"] == "v6_medium"
        assert read_json("jobs")["features"]["skland"] is False
    finally:
        db.close()
        engine.dispose()


def test_import_env_smtp_when_no_db_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core import file_config as fc
    from app.core.database import Base
    from app.models.system_config import SystemConfig
    from app.services import config_import as ci
    from app.services.config_import import import_legacy_system_configs

    install = tmp_path / "install"
    install.mkdir()
    (install / ".env").write_text(
        "SMTP_HOST=smtp.env.example\nSMTP_FROM=a@b.c\nSMTP_PASSWORD=env-pw\n"
        "STEAM_API_KEY=from-env-steam\nICP_BEIAN_NO=env备案\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ci, "resolve_install_dir", lambda: install)
    fc.set_config_dir_for_tests(install / "config")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(
        SystemConfig(
            key="integrations",
            value=json.dumps({"qq_app_id": "10001"}),
        )
    )
    db.commit()
    try:
        import_legacy_system_configs(db)
        email = read_json("email")
        assert email is not None
        assert email["smtp_host"] == "smtp.env.example"
        assert email["smtp_password"] == "env-pw"
        integ = read_json("integrations")
        assert integ is not None
        assert integ["steam_api_key"] == "from-env-steam"
        assert integ["qq_app_id"] == "10001"
        assert read_json("auth")["icp_beian_no"] == "env备案"
    finally:
        db.close()
        engine.dispose()
