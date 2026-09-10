"""Pelican 集成密钥读写。"""

from app.core.file_config import write_json
from app.services import integrations_config as ic


def test_pelican_fields_default_empty() -> None:
    cfg = ic.load_integrations()
    pub = ic.public_integrations(cfg)
    assert pub["pelican_configured"] is False
    assert pub["pelican_client_token_set"] is False


def test_pelican_token_from_file() -> None:
    write_json(
        "integrations",
        {
            "pelican_base_url": "https://panel.example.com/api/client",
            "pelican_client_token": "ptlc_secret",
            "pelican_server_uuid": "abcd1234",
        },
    )
    cfg = ic.load_integrations()
    assert cfg["pelican_client_token"] == "ptlc_secret"
    assert cfg["pelican_base_url"] == "https://panel.example.com"
    pub = ic.public_integrations(cfg)
    assert pub["pelican_configured"] is True
