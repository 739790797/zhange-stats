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


def test_application_server_ref_matches_uuid() -> None:
    from app.services.minecraft.pelican import application_server_ref

    payload = {
        "data": [
            {"attributes": {"id": 1, "uuid": "other", "egg": 3}},
            {
                "attributes": {
                    "id": 48,
                    "uuid": "dec0e70d-8e07-48a9-b294-79c33b91587a",
                    "egg": 22,
                    "skip_scripts": False,
                }
            },
        ]
    }
    found = application_server_ref(payload, "DEC0E70D-8E07-48A9-B294-79C33B91587A")
    assert found == {"id": 48, "egg": 22, "skip_scripts": False}
    assert application_server_ref(payload, "missing") is None


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
