"""旧 .env / system_configs 迁入 config/：模板建出来的文件不挡导入，管理员已配的值不被覆盖，只迁一次。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config_sync import sync_site_config
from app.core.crypto_secret import encrypt_secret
from app.core.database import Base
from app.core.file_config import read_json, write_json
from app.models.system_config import SystemConfig
from app.services import config_import as ci
from app.services.auth_config import load_auth_config
from app.services.config_import import import_legacy_system_configs
from app.services.email_config import load_email_config
from app.services.integrations_config import (
    get_minecraft_public_address,
    get_minecraft_rcon_credentials,
    load_integrations,
    save_integrations,
)
from app.services.scheduler_config import load_scheduler_config


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "install"
    root.mkdir()
    monkeypatch.setattr(ci, "resolve_install_dir", lambda: root)
    return root


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _rows(db: Session, **rows: dict) -> None:
    for key, value in rows.items():
        db.add(SystemConfig(key=key, value=json.dumps(value, ensure_ascii=False)))
    db.commit()


def test_template_created_files_do_not_block_the_import(install: Path, db: Session) -> None:
    assert {"email", "integrations", "auth", "ocr", "jobs"} <= set(sync_site_config())
    _rows(
        db,
        integrations={
            "steam_api_key": encrypt_secret("S" * 32),
            "minecraft_public_host": "mc.example.com",
            "minecraft_public_port": 25566,
        },
        email_smtp={
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "bot@example.com",
            "smtp_password": encrypt_secret("smtp-pw"),
            "encryption": "STARTTLS",
        },
        auth_session={"access_token_expire_minutes": 60},
        site={"icp_beian_no": "测ICP备1号"},
        ocr={"paddle_profile": "v5_mobile", "engines": {"paddle": True, "easyocr": False}},
        scheduler_jobs={"steam_presence": {"enabled": False, "interval_minutes": 5}},
        platform_features={"features": {"skland": False}},
    )

    import_legacy_system_configs(db)

    assert get_minecraft_public_address() == ("mc.example.com", 25566)
    assert load_integrations()["steam_api_key"] == "S" * 32
    email = load_email_config()
    assert (email["enabled"], email["smtp_host"], email["smtp_port"]) == (True, "smtp.example.com", 587)
    assert (email["encryption"], email["smtp_password"]) == ("STARTTLS", "smtp-pw")
    auth = load_auth_config()
    assert (auth["access_token_expire_minutes"], auth["icp_beian_no"]) == (60, "测ICP备1号")
    assert read_json("ocr")["engines"] == {"paddle": True, "easyocr": False}
    assert load_scheduler_config()["steam_presence"] == {"enabled": False, "interval_minutes": 5}
    assert read_json("jobs")["features"] == {"skland": False}
    assert read_json("integrations")["_version"] == 1


def test_values_the_admin_already_set_are_kept(install: Path, db: Session) -> None:
    sync_site_config()
    save_integrations(None, {"steam_api_key": "user-steam", "minecraft_public_host": "new.example.com"})
    email = read_json("email")
    email.update(
        enabled=True,
        smtp_host="smtp.new.example",
        smtp_user="new@example.com",
        smtp_password="new-pw",
    )
    write_json("email", email)
    write_json("auth", {**read_json("auth"), "min_password_length": 12})
    _rows(
        db,
        integrations={
            "steam_api_key": encrypt_secret("legacy-steam"),
            "minecraft_public_host": "old.example.com",
            "minecraft_public_port": 25566,
            "minecraft_rcon_host": "rcon.old.example",
            "minecraft_rcon_password": encrypt_secret("rcon-pw"),
        },
        email_smtp={
            "enabled": True,
            "smtp_host": "smtp.old.example",
            "smtp_port": 587,
            "smtp_password": encrypt_secret("old-pw"),
            "encryption": "STARTTLS",
            "code_expire_minutes": 30,
        },
        auth_session={"min_password_length": 10, "enforce_single_admin": True},
    )

    import_legacy_system_configs(db)

    assert load_integrations()["steam_api_key"] == "user-steam"
    # 新主机不配旧端口：同组有一项改过就整组保留
    assert get_minecraft_public_address() == ("new.example.com", 25565)
    assert get_minecraft_rcon_credentials() == ("rcon.old.example", 25575, "rcon-pw")
    email = load_email_config()
    assert (email["smtp_host"], email["smtp_port"], email["encryption"]) == ("smtp.new.example", 465, "SSL")
    assert email["smtp_password"] == "new-pw"
    assert email["code_expire_minutes"] == 30
    auth = load_auth_config()
    assert (auth["min_password_length"], auth["enforce_single_admin"]) == (12, True)


def test_import_runs_once_per_database(install: Path, db: Session) -> None:
    sync_site_config()
    _rows(
        db,
        integrations={
            "minecraft_rcon_host": "rcon.example",
            "minecraft_rcon_password": encrypt_secret("rcon-pw"),
        },
    )
    import_legacy_system_configs(db)
    assert get_minecraft_rcon_credentials() == ("rcon.example", 25575, "rcon-pw")
    assert db.get(SystemConfig, "legacy_config_imported") is not None

    save_integrations(None, {"minecraft_rcon_host": "", "clear_minecraft_rcon_password": True})
    import_legacy_system_configs(db)

    assert get_minecraft_rcon_credentials() == ("", 25575, "")


def test_env_fallbacks_follow_the_old_reading(install: Path, db: Session) -> None:
    (install / ".env").write_text(
        "SMTP_HOST=smtp.env.example\nSMTP_FROM=a@b.c\nSMTP_PASSWORD=env-pw\n"
        "STEAM_API_KEY=env-steam\nREJECT_WEAK_ADMIN_PASSWORD=true\nACCESS_TOKEN_EXPIRE_MINUTES=120\n",
        encoding="utf-8",
    )
    sync_site_config()
    _rows(
        db,
        email_smtp={"smtp_host": "smtp.db.example", "smtp_password": ""},
        integrations={"steam_api_key": "", "qq_app_id": "10001"},
        auth_session={"reject_weak_admin_password": None, "access_token_expire_minutes": None},
    )

    import_legacy_system_configs(db)

    email = load_email_config()
    # 库里有值盖过 .env；空口令回落 .env
    assert (email["smtp_host"], email["smtp_password"], email["smtp_from"]) == (
        "smtp.db.example",
        "env-pw",
        "a@b.c",
    )
    integ = load_integrations()
    assert (integ["steam_api_key"], integ["qq_app_id"]) == ("env-steam", "10001")
    auth = load_auth_config()
    # 旧版库里 null 是「自动」，盖过 .env 的 true；其余 null 回落 .env
    assert auth["reject_weak_admin_password"] is None
    assert auth["access_token_expire_minutes"] == 120


def test_jobs_sections_import_separately(install: Path, db: Session) -> None:
    sync_site_config()
    admin_sched = {"steam_presence": {"enabled": True, "interval_minutes": 7}}
    write_json("jobs", {**read_json("jobs"), "scheduler": admin_sched})
    _rows(
        db,
        scheduler_jobs={"steam_presence": {"enabled": False, "interval_minutes": 5}},
        platform_features={"steam": False},
    )

    import_legacy_system_configs(db)

    jobs = read_json("jobs")
    assert jobs["scheduler"] == admin_sched
    assert jobs["features"] == {"steam": False}
