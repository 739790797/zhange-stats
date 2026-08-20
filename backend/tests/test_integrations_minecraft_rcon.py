"""Minecraft RCON 作为集成密钥读写。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.core.crypto_secret import encrypt_secret
from app.services import integrations_config as ic


def _db_with_stored(stored: dict | None) -> MagicMock:
    db = MagicMock()
    row = None
    if stored is not None:
        row = MagicMock()
        row.value = json.dumps(stored, ensure_ascii=False)
    q = db.query.return_value
    q.filter.return_value.first.return_value = row
    return db


def test_rcon_fields_default_empty(monkeypatch):
    monkeypatch.setattr(
        ic,
        "_env_defaults",
        lambda: {
            "steam_api_key": "",
            "qq_app_id": "",
            "qq_app_key": "",
            "napcat_base_url": "",
            "napcat_token": "",
            "github_token": "",
            "pelican_base_url": "",
            "pelican_client_token": "",
            "pelican_server_uuid": "",
            "minecraft_rcon_host": "",
            "minecraft_rcon_port": "25575",
            "minecraft_rcon_password": "",
        },
    )
    cfg = ic.load_integrations(_db_with_stored(None))
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_rcon_configured"] is False
    assert pub["minecraft_rcon_password_set"] is False
    assert pub["minecraft_rcon_port"] == 25575


def test_rcon_password_decrypts(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-rcon")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            ic,
            "_env_defaults",
            lambda: {
                "steam_api_key": "",
                "qq_app_id": "",
                "qq_app_key": "",
                "napcat_base_url": "",
                "napcat_token": "",
                "github_token": "",
                "pelican_base_url": "",
                "pelican_client_token": "",
                "pelican_server_uuid": "",
                "minecraft_rcon_host": "",
                "minecraft_rcon_port": "25575",
                "minecraft_rcon_password": "",
            },
        )
        enc = encrypt_secret("rcon-secret")
        cfg = ic.load_integrations(
            _db_with_stored(
                {
                    "minecraft_rcon_host": "127.0.0.1",
                    "minecraft_rcon_port": 25580,
                    "minecraft_rcon_password": enc,
                }
            )
        )
        assert cfg["minecraft_rcon_password"] == "rcon-secret"
        host, port, password = ic.get_minecraft_rcon_credentials(
            _db_with_stored(
                {
                    "minecraft_rcon_host": "127.0.0.1",
                    "minecraft_rcon_port": 25580,
                    "minecraft_rcon_password": enc,
                }
            )
        )
        assert host == "127.0.0.1"
        assert port == 25580
        assert password == "rcon-secret"
        pub = ic.public_integrations(cfg)
        assert pub["minecraft_rcon_configured"] is True
    finally:
        get_settings.cache_clear()
