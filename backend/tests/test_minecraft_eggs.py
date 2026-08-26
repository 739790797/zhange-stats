from app.services.minecraft.eggs import infer_loader
from app.services.minecraft.pelican import (
    parse_application_server,
    startup_command,
    startup_details,
)


def test_infer_loader_prefers_neoforge_over_forge():
    assert infer_loader("java -jar neoforge-21.1.jar") == "neoforge"
    assert infer_loader("FORGE_VERSION=47.2.0") == "forge"
    assert infer_loader("fabric-loader-0.16") == "fabric"


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
