"""Shared fakes for integrations_config tests. Do not copy `_db_with_stored`."""

from __future__ import annotations

import json
from unittest.mock import MagicMock


def empty_env_defaults(**overrides: str) -> dict[str, str]:
    base = {
        "steam_api_key": "",
        "qq_app_id": "",
        "qq_app_key": "",
        "github_token": "",
        "pelican_base_url": "",
        "pelican_client_token": "",
        "pelican_application_token": "",
        "pelican_server_uuid": "",
        "minecraft_rcon_host": "",
        "minecraft_rcon_port": "25575",
        "minecraft_rcon_password": "",
        "minecraft_public_host": "",
        "minecraft_public_port": "25565",
    }
    base.update(overrides)
    return base


def db_with_stored(stored: dict | None) -> MagicMock:
    db = MagicMock()
    row = None
    if stored is not None:
        row = MagicMock()
        row.value = json.dumps(stored, ensure_ascii=False)
    q = db.query.return_value
    q.filter.return_value.first.return_value = row
    return db
