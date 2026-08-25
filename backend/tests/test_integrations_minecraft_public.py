"""Minecraft public join address as integrations secrets."""

from __future__ import annotations

from app.services import integrations_config as ic

from tests.integrations_fakes import db_with_stored, empty_env_defaults


def test_public_address_defaults_empty(monkeypatch):
    monkeypatch.setattr(ic, "_env_defaults", empty_env_defaults)
    cfg = ic.load_integrations(db_with_stored(None))
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_public_configured"] is False
    assert pub["minecraft_public_host"] == ""
    assert pub["minecraft_public_port"] == 25565


def test_public_address_reads_stored(monkeypatch):
    monkeypatch.setattr(ic, "_env_defaults", empty_env_defaults)
    stored = {
        "minecraft_public_host": "mc.example.com",
        "minecraft_public_port": 25566,
    }
    cfg = ic.load_integrations(db_with_stored(stored))
    assert cfg["minecraft_public_host"] == "mc.example.com"
    host, port = ic.get_minecraft_public_address(db_with_stored(stored))
    assert host == "mc.example.com"
    assert port == 25566
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_public_configured"] is True
    assert pub["minecraft_public_port"] == 25566
