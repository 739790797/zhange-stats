"""Minecraft public join address as integrations secrets."""

from app.core.file_config import write_json
from app.services import integrations_config as ic


def test_public_address_defaults_empty() -> None:
    cfg = ic.load_integrations()
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_public_configured"] is False
    assert pub["minecraft_public_host"] == ""
    assert pub["minecraft_public_port"] == 25565


def test_public_address_reads_stored() -> None:
    write_json(
        "integrations",
        {
            "minecraft_public_host": "mc.example.com",
            "minecraft_public_port": 25566,
        },
    )
    cfg = ic.load_integrations()
    assert cfg["minecraft_public_host"] == "mc.example.com"
    host, port = ic.get_minecraft_public_address()
    assert host == "mc.example.com"
    assert port == 25566
    pub = ic.public_integrations(cfg)
    assert pub["minecraft_public_configured"] is True
    assert pub["minecraft_public_port"] == 25566
