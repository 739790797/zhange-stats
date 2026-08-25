"""Minecraft RCON 作为集成密钥读写。"""

from __future__ import annotations

from app.core.crypto_secret import encrypt_secret
from app.services import integrations_config as ic

from tests.integrations_fakes import db_with_stored, empty_env_defaults


def test_rcon_fields_default_empty(monkeypatch):
    monkeypatch.setattr(ic, "_env_defaults", empty_env_defaults)
    cfg = ic.load_integrations(db_with_stored(None))
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_rcon_configured"] is False
    assert pub["minecraft_rcon_password_set"] is False
    assert pub["minecraft_rcon_port"] == 25575


def test_rcon_password_decrypts(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-rcon")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        monkeypatch.setattr(ic, "_env_defaults", empty_env_defaults)
        enc = encrypt_secret("rcon-secret")
        stored = {
            "minecraft_rcon_host": "127.0.0.1",
            "minecraft_rcon_port": 25580,
            "minecraft_rcon_password": enc,
        }
        cfg = ic.load_integrations(db_with_stored(stored))
        assert cfg["minecraft_rcon_password"] == "rcon-secret"
        host, port, password = ic.get_minecraft_rcon_credentials(db_with_stored(stored))
        assert host == "127.0.0.1"
        assert port == 25580
        assert password == "rcon-secret"
        pub = ic.public_integrations(cfg)
        assert pub["minecraft_rcon_configured"] is True
    finally:
        get_settings.cache_clear()
