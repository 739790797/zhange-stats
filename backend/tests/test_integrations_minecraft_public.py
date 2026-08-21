"""Minecraft public join address as integrations secrets."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

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


def test_public_address_defaults_empty(monkeypatch):
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
            "minecraft_public_host": "",
            "minecraft_public_port": "25565",
        },
    )
    cfg = ic.load_integrations(_db_with_stored(None))
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_public_configured"] is False
    assert pub["minecraft_public_host"] == ""
    assert pub["minecraft_public_port"] == 25565


def test_public_address_reads_stored(monkeypatch):
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
            "minecraft_public_host": "",
            "minecraft_public_port": "25565",
        },
    )
    stored = {
        "minecraft_public_host": "mc.example.com",
        "minecraft_public_port": 25566,
    }
    cfg = ic.load_integrations(_db_with_stored(stored))
    assert cfg["minecraft_public_host"] == "mc.example.com"
    host, port = ic.get_minecraft_public_address(_db_with_stored(stored))
    assert host == "mc.example.com"
    assert port == 25566
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_public_configured"] is True
    assert pub["minecraft_public_port"] == 25566
