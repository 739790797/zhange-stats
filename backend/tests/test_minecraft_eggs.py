from app.services.minecraft.eggs import infer_loader, pick_egg, score_egg, wrap_boot_command
from app.services.minecraft.pelican import (
    parse_application_server,
    startup_command,
    startup_details,
)


def test_infer_loader_prefers_neoforge_over_forge():
    assert infer_loader("java -jar neoforge-21.1.jar") == "neoforge"
    assert infer_loader("FORGE_VERSION=47.2.0") == "forge"
    assert infer_loader("fabric-loader-0.16") == "fabric"


def test_pick_egg_matches_loader_not_neighbors():
    eggs = [
        {
            "name": "Forge",
            "description": "Minecraft Forge",
            "nest": "Minecraft",
            "startup": "",
            "docker_images": [],
        },
        {
            "name": "NeoForge",
            "description": "Minecraft NeoForge",
            "nest": "Minecraft",
            "startup": "",
            "docker_images": [],
        },
        {
            "name": "Fabric",
            "description": "",
            "nest": "Minecraft",
            "startup": "java -jar fabric-server.jar",
            "docker_images": [],
        },
    ]
    assert pick_egg(eggs, "neoforge")["name"] == "NeoForge"
    assert pick_egg(eggs, "forge")["name"] == "Forge"
    assert pick_egg(eggs, "fabric")["name"] == "Fabric"
    assert score_egg(eggs[0], "neoforge") == 0


def test_startup_details_reads_variables_and_images():
    data = {
        "data": [
            {
                "attributes": {
                    "name": "Minecraft Version",
                    "env_variable": "MINECRAFT_VERSION",
                    "server_value": "1.21.1",
                    "default_value": "latest",
                }
            }
        ],
        "meta": {
            "startup_command": "java -jar {{SERVER_JARFILE}}",
            "docker_images": {"Java 21": "ghcr.io/pelican-eggs/yolks:java_21"},
        },
    }
    assert startup_command(data) == "java -jar {{SERVER_JARFILE}}"
    details = startup_details(data)
    assert details["variables"][0]["key"] == "MINECRAFT_VERSION"
    assert details["variables"][0]["value"] == "1.21.1"
    assert "java_21" in details["docker_images"][0]


def test_wrap_boot_command_is_idempotent():
    raw = "java -jar {{SERVER_JARFILE}}"
    wrapped = wrap_boot_command(raw)
    assert wrapped.startswith("bash zhange/boot.sh ")
    assert wrap_boot_command(wrapped) == wrapped
    assert "zhange/boot.sh" in wrap_boot_command("", fallback=raw)


def test_parse_application_server_reads_container():
    parsed = parse_application_server(
        {
            "attributes": {
                "id": 7,
                "uuid": "abc",
                "egg": 12,
                "container": {
                    "startup_command": "java -jar server.jar",
                    "image": "ghcr.io/example:java21",
                    "environment": {"MINECRAFT_VERSION": "1.21.1", "SKIP": None},
                },
            }
        }
    )
    assert parsed["id"] == 7
    assert parsed["egg_id"] == 12
    assert parsed["startup"] == "java -jar server.jar"
    assert parsed["environment"]["MINECRAFT_VERSION"] == "1.21.1"
    assert parsed["environment"]["SKIP"] == ""


def test_collect_eggs_does_not_inspect_current_server(monkeypatch):
    from app.services.minecraft import eggs as eggs

    monkeypatch.setattr(
        eggs,
        "get_pelican_credentials",
        lambda db: ("https://panel.example", "client", "uuid"),
    )
    monkeypatch.setattr(eggs, "get_pelican_application_token", lambda db: "app-token")

    def fake_list(base, token):
        assert base == "https://panel.example"
        assert token == "app-token"
        return [
            {
                "egg_id": 9,
                "name": "Fabric",
                "description": "Minecraft Fabric",
                "nest": "Minecraft",
                "startup": "java -jar fabric.jar",
                "docker_images": ["java"],
            }
        ]

    monkeypatch.setattr(eggs.pelican, "list_application_eggs", fake_list)

    def boom(*_args, **_kwargs):
        raise AssertionError("playbook egg list must not touch the current server")

    monkeypatch.setattr(eggs, "inspect_current_egg", boom)
    monkeypatch.setattr(eggs, "_resolve_application_server", boom)

    data = eggs.collect_eggs(object(), loader="fabric")
    assert data["message"] == ""
    assert data["application_configured"] is True
    assert data["eggs"][0]["egg_id"] == 9
    assert data["current"]["command"] == ""
    assert data["recommended"]["egg_id"] == 9
