"""Pelican 集成密钥读写。"""

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


def test_pelican_fields_default_empty(monkeypatch):
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
        },
    )
    cfg = ic.load_integrations(_db_with_stored(None))
    pub = ic.public_integrations(cfg)
    assert pub["pelican_configured"] is False
    assert pub["pelican_client_token_set"] is False


def test_pelican_token_decrypts(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-pelican-token")
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
            },
        )
        enc = encrypt_secret("ptlc_secret")
        cfg = ic.load_integrations(
            _db_with_stored(
                {
                    "pelican_base_url": "https://panel.example.com/api/client",
                    "pelican_client_token": enc,
                    "pelican_server_uuid": "abcd1234",
                }
            )
        )
        assert cfg["pelican_client_token"] == "ptlc_secret"
        assert cfg["pelican_base_url"] == "https://panel.example.com"
        pub = ic.public_integrations(cfg)
        assert pub["pelican_configured"] is True
    finally:
        get_settings.cache_clear()
