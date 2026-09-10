"""Minecraft RCON 作为集成密钥读写。"""

from app.core.file_config import write_json
from app.services import integrations_config as ic


def test_rcon_fields_default_empty() -> None:
    cfg = ic.load_integrations()
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_rcon_configured"] is False
    assert pub["minecraft_rcon_password_set"] is False
    assert pub["minecraft_rcon_port"] == 25575


def test_rcon_password_from_file() -> None:
    write_json(
        "integrations",
        {
            "minecraft_rcon_host": "127.0.0.1",
            "minecraft_rcon_port": 25580,
            "minecraft_rcon_password": "rcon-secret",
        },
    )
    cfg = ic.load_integrations()
    assert cfg["minecraft_rcon_password"] == "rcon-secret"
    host, port, password = ic.get_minecraft_rcon_credentials()
    assert host == "127.0.0.1"
    assert port == 25580
    assert password == "rcon-secret"
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_rcon_configured"] is True
