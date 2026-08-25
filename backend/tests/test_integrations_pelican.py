"""Pelican 集成密钥读写。"""

from __future__ import annotations

from app.core.crypto_secret import encrypt_secret
from app.services import integrations_config as ic

from tests.integrations_fakes import db_with_stored, empty_env_defaults


def test_pelican_fields_default_empty(monkeypatch):
    monkeypatch.setattr(ic, "_env_defaults", empty_env_defaults)
    cfg = ic.load_integrations(db_with_stored(None))
    pub = ic.public_integrations(cfg)
    assert pub["pelican_configured"] is False
    assert pub["pelican_client_token_set"] is False


def test_pelican_token_decrypts(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-pelican-token")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        monkeypatch.setattr(ic, "_env_defaults", empty_env_defaults)
        enc = encrypt_secret("ptlc_secret")
        cfg = ic.load_integrations(
            db_with_stored(
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
