"""Minecraft 模组探测 / Chunky 指令白名单。"""

from __future__ import annotations

import pytest

from app.services.minecraft_mod_registry import (
    SPECS,
    assemble_mod_command,
    command_tree_out,
    config_directory,
    config_directory_abs,
    curseforge_url,
    install_directory,
    jar_matches_spec,
    spec_links_out,
    version_from_jar,
)
from app.services.minecraft_mod_tools import (
    build_chunky_commands,
    is_unknown_command,
    parse_chunky_state,
)


def _chunky():
    return next(spec for spec in SPECS if spec.id == "chunky")


@pytest.mark.parametrize(
    ("filename", "matched"),
    [
        ("Chunky-NeoForge-1.4.23.jar", True),
        ("chunky-fabric-1.3.146.jar", True),
        ("Chunky-1.4.40.jar", True),
        ("Chunky-Bukkit-1.4.28.jar", True),
        ("Chunky.jar", True),
        ("ChunkyBorder-1.2.13.jar", False),
        ("chunky-border-1.2.jar", False),
        ("lithium-fabric-0.12.7.jar", False),
        ("DistantHorizons-2.3.0.jar", False),
    ],
)
def test_jar_matches_chunky_ignores_loader(filename: str, matched: bool):
    assert jar_matches_spec(filename, _chunky()) is matched


def test_parse_chunky_progress_running():
    raw = (
        "Task running for minecraft:overworld.\n"
        "World: world Shape: square Center: 0, 0 Radius: 500\n"
        "12345 / 251001 chunks (4.92%) Rate: 123.4 cps ETA: 00:12:34 Chunk: 12, -34\n"
    )
    parsed = parse_chunky_state(raw)
    assert parsed["state"] == "running"
    assert parsed["world"] == "world"
    assert parsed["shape"] == "square"
    assert parsed["center_x"] == 0
    assert parsed["center_z"] == 0
    assert parsed["radius"] == 500
    assert parsed["percent"] == 4.92
    assert parsed["chunks"] == 12345
    assert parsed["chunks_total"] == 251001
    assert parsed["rate"] == 123.4
    assert parsed["eta"] == "00:12:34"
    assert parsed["chunk_x"] == 12
    assert parsed["chunk_z"] == -34


def test_parse_chunky_idle_and_paused():
    assert parse_chunky_state("No tasks are currently running.")["state"] == "idle"
    assert parse_chunky_state("Task paused for world.")["state"] == "paused"


def test_parse_chunky_needs_confirm():
    raw = "Cancelled 1 tasks. Please type '/chunky confirm' to confirm."
    parsed = parse_chunky_state(raw)
    assert parsed["needs_confirm"] is True


def test_unknown_command_hints():
    assert is_unknown_command("Unknown or incomplete command, see below for error")
    assert is_unknown_command("Unknown command. Type \"/help\" for help.")
    assert not is_unknown_command("Task running for world.")


def test_build_chunky_start_one_liner():
    cmds = build_chunky_commands(
        "start",
        world="world",
        shape="square",
        center_x=0,
        center_z=0,
        radius=1000,
    )
    assert cmds == ["chunky start world square 0 0 1000"]


def test_build_chunky_apply_sequence():
    cmds = build_chunky_commands(
        "apply",
        world="minecraft:the_nether",
        shape="circle",
        center_x=32,
        center_z=-64,
        radius=2000,
        pattern="concentric",
    )
    assert cmds == [
        "chunky world minecraft:the_nether",
        "chunky shape circle",
        "chunky center 32 -64",
        "chunky radius 2000",
        "chunky pattern concentric",
        "chunky selection",
    ]


def test_build_chunky_rejects_bad_world():
    with pytest.raises(Exception, match="世界名"):
        build_chunky_commands("pause", world="world; stop")


def test_build_chunky_simple_actions():
    assert build_chunky_commands("progress") == ["chunky progress"]
    assert build_chunky_commands("pause", world="world") == ["chunky pause world"]
    assert build_chunky_commands("spawn") == ["chunky spawn"]


def test_assemble_chunky_command_tree():
    spec = _chunky()
    assert assemble_mod_command(spec, "spawn") == "chunky spawn"
    assert assemble_mod_command(spec, "world", {"world": "minecraft:the_nether"}) == (
        "chunky world minecraft:the_nether"
    )
    assert assemble_mod_command(spec, "shape", {"shape": "circle"}) == "chunky shape circle"
    assert assemble_mod_command(spec, "center", {"x": 32, "z": -64}) == "chunky center 32 -64"
    assert assemble_mod_command(spec, "worldborder", {}) == "chunky worldborder"
    assert assemble_mod_command(spec, "worldborder", {"world": "world"}) == (
        "chunky worldborder world"
    )
    tree = command_tree_out(spec)
    ids = [row["id"] for row in tree]
    assert "start" not in ids
    assert "pause" not in ids
    assert "spawn" in ids
    assert "trim" in ids
    assert config_directory_abs("neoforge", spec) == "/config/chunky"


def test_assemble_chunky_rejects_injection():
    spec = _chunky()
    with pytest.raises(Exception, match="世界"):
        assemble_mod_command(spec, "world", {"world": "world; stop"})
    with pytest.raises(Exception, match="指令"):
        assemble_mod_command(spec, "start")
    with pytest.raises(Exception, match="形状"):
        assemble_mod_command(spec, "shape", {"shape": "nope"})


def test_chunky_catalog_links_and_version():
    spec = _chunky()
    assert spec.links.modrinth_id == "fALzjamp"
    assert "modrinth.com/mod/chunky" in spec_links_out(spec, "neoforge")["modrinth_url"]
    assert curseforge_url("neoforge", spec).endswith("chunky-pregenerator-forge")
    assert curseforge_url("fabric", spec).endswith("chunky-pregenerator")
    assert version_from_jar("Chunky-NeoForge-1.4.23.jar") == "1.4.23"
    assert install_directory("neoforge", spec) == "/mods"
    assert install_directory("paper", spec) == "/plugins"
    assert config_directory("neoforge", spec) == "config/chunky"
    assert config_directory("paper", spec) == "plugins/Chunky"
    assert config_directory("neoforge", spec, present_directory="/plugins") == "plugins/Chunky"


def test_collect_detects_chunky_plugin_without_rcon(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc,
        "_scan_files",
        lambda _db, force=False: {
            "pelican_configured": True,
            "jars": [
                {
                    "filename": "Chunky-1.4.40.jar",
                    "directory": "/plugins",
                    "kind": "plugin",
                },
                {
                    "filename": "spark.jar",
                    "directory": "/plugins",
                    "kind": "plugin",
                },
            ],
            "worlds": ["world"],
            "message": "",
        },
    )
    monkeypatch.setattr(svc, "_rcon_creds", lambda _db: ("127.0.0.1", 25575, ""))
    monkeypatch.setattr(
        svc,
        "_server_context",
        lambda _db: {"loader": "paper", "mc_version": "1.21.1"},
    )
    monkeypatch.setattr(
        svc,
        "lookup_latest_pin",
        lambda spec, loader="", mc_version="": {
            "version_number": "1.4.40",
            "filename": "Chunky-1.4.40.jar",
        },
    )
    data = svc.collect_mod_tools(object())
    chunky = next(row for row in data["tools"] if row["id"] == "chunky")
    assert chunky["present"] is True
    assert chunky["loaded"] is False
    assert chunky["filename"] == "Chunky-1.4.40.jar"
    assert chunky["kind"] == "plugin"
    assert chunky["links"]["modrinth_url"].endswith("/mod/chunky")
    assert chunky["catalog"]["installed_version"] == "1.4.40"
    assert chunky["catalog"]["update_available"] is False
    assert chunky["presets"][0]["id"] == "zhange"


def test_collect_ignores_unrelated_jars(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc,
        "_scan_files",
        lambda _db, force=False: {
            "pelican_configured": True,
            "jars": [
                {
                    "filename": "lithium-fabric-0.12.7.jar",
                    "directory": "/mods",
                    "kind": "mod",
                }
            ],
            "worlds": [],
            "message": "",
        },
    )
    monkeypatch.setattr(svc, "_rcon_creds", lambda _db: ("", 25575, ""))
    monkeypatch.setattr(svc, "lookup_latest_pin", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        svc, "_server_context", lambda _db: {"loader": "neoforge", "mc_version": "1.21.1"}
    )
    data = svc.collect_mod_tools(object())
    chunky = next(row for row in data["tools"] if row["id"] == "chunky")
    assert chunky["present"] is False
    assert chunky["links"]["modrinth_url"].endswith("/mod/chunky")
    assert chunky["links"]["curseforge_url"].endswith("chunky-pregenerator-forge")
    assert chunky["catalog"]["target_directory"] == "/mods"


def test_mc_version_skips_latest_placeholder():
    from app.services.minecraft_mod_tools import _mc_version_from_variables

    assert (
        _mc_version_from_variables(
            [
                {"key": "MINECRAFT_VERSION", "value": "latest"},
                {"key": "MC_VERSION", "value": "1.21.1"},
            ]
        )
        == "1.21.1"
    )
    assert _mc_version_from_variables([{"key": "VANILLA_VERSION", "value": "1.21.1"}]) == "1.21.1"
    assert _mc_version_from_variables([{"key": "VERSION", "value": "latest-release"}]) == ""


def test_infer_runtime_loader_plugins_and_neoforge():
    from app.services.minecraft_mod_tools import _infer_runtime_loader

    assert _infer_runtime_loader("java -jar neoforge-21.1.jar") == "neoforge"
    assert _infer_runtime_loader("paper-1.21.1.jar") == "paper"
    assert _infer_runtime_loader("purpur-1.21.1.jar") == "purpur"


def test_catalog_same_version_is_not_update_even_if_filename_differs(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc,
        "lookup_latest_pin",
        lambda spec, loader="", mc_version="": {
            "version_number": "1.4.23",
            "filename": "Chunky-Fabric-1.4.23.jar",
        },
    )
    out = svc._catalog_out(
        _chunky(),
        loader="neoforge",
        mc_version="1.21.1",
        filename="Chunky-NeoForge-1.4.23.jar",
        directory="/mods",
    )
    assert out["installed_version"] == "1.4.23"
    assert out["latest_version"] == "1.4.23"
    assert out["update_available"] is False
    assert out["loader"] == "neoforge"


def test_catalog_newer_version_is_update(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc,
        "lookup_latest_pin",
        lambda spec, loader="", mc_version="": {
            "version_number": "1.4.23",
            "filename": "Chunky-NeoForge-1.4.23.jar",
        },
    )
    out = svc._catalog_out(
        _chunky(),
        loader="neoforge",
        mc_version="1.21.1",
        filename="Chunky-NeoForge-1.4.20.jar",
        directory="/mods",
    )
    assert out["update_available"] is True


def test_server_context_is_current_server_only(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc, "_live_egg_context", lambda _db: {"loader": "neoforge", "mc_version": "1.21.1"}
    )
    assert svc._server_context(object()) == {"loader": "neoforge", "mc_version": "1.21.1"}
    assert not hasattr(svc, "_applied_context")


def test_server_context_stays_empty_when_live_unknown(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(svc, "_live_egg_context", lambda _db: {"loader": "", "mc_version": ""})
    assert svc._server_context(object()) == {"loader": "", "mc_version": ""}


def test_live_egg_context_reads_inspect(monkeypatch):
    from app.services import minecraft_mod_tools as svc
    from app.services import minecraft_eggs as eggs
    from app.services import pelican_client as pelican

    monkeypatch.setattr(svc, "get_pelican_credentials", lambda _db: ("https://p", "tok", "uuid"))
    monkeypatch.setattr(pelican, "pelican_configured", lambda *_a: True)
    monkeypatch.setattr(
        eggs,
        "inspect_current_egg",
        lambda *_a, **_k: {
            "inferred_loader": "neoforge",
            "command": "java -jar neoforge-21.1.jar",
            "docker_images": [],
            "variables": [{"key": "MINECRAFT_VERSION", "value": "1.21.1"}],
        },
    )
    assert svc._live_egg_context(object()) == {"loader": "neoforge", "mc_version": "1.21.1"}


def test_live_context_uses_root_installer_when_egg_is_generic(monkeypatch):
    from app.services import minecraft_mod_tools as svc
    from app.services import minecraft_eggs as eggs
    from app.services import pelican_client as pelican

    monkeypatch.setattr(svc, "get_pelican_credentials", lambda _db: ("https://p", "tok", "uuid"))
    monkeypatch.setattr(pelican, "pelican_configured", lambda *_a: True)
    monkeypatch.setattr(
        eggs,
        "inspect_current_egg",
        lambda *_a, **_k: {
            "inferred_loader": "",
            "command": "bash run.sh",
            "docker_images": [],
            "variables": [{"key": "VANILLA_VERSION", "value": "1.21.1"}],
        },
    )
    monkeypatch.setattr(
        pelican,
        "list_files",
        lambda *_a, **_k: [
            {"name": "mods"},
            {"name": "server.jar"},
            {"name": "neoforge-21.1.248-installer.jar"},
        ],
    )
    assert svc._live_egg_context(object()) == {"loader": "neoforge", "mc_version": "1.21.1"}


def test_live_disk_loader_reads_libraries_net(monkeypatch):
    from app.services import minecraft_mod_tools as svc
    from app.services import pelican_client as pelican

    def fake_list(_base, _token, _uuid, directory):
        if directory == "/":
            return [{"name": "libraries"}, {"name": "mods"}]
        if directory == "/libraries/net":
            return [{"name": "neoforged"}, {"name": "minecraft"}]
        return []

    monkeypatch.setattr(pelican, "list_files", fake_list)
    assert svc._live_disk_loader("https://p", "tok", "uuid") == "neoforge"


def test_chunky_factory_file_follows_loader():
    from app.services.minecraft_mod_registry import (
        preset_by_id,
        preset_file_for_loader,
        resolve_preset_body,
        upsert_draft_content,
    )

    spec = _chunky()
    preset = preset_by_id(spec, "zhange")
    assert preset is not None
    mod_name, mod_body = preset_file_for_loader(preset, "neoforge", spec)
    assert mod_name == "config.json"
    assert "continueOnRestart" in mod_body
    plugin_name, plugin_body = preset_file_for_loader(preset, "paper", spec)
    assert plugin_name == "config.yml"
    assert "continue-on-restart" in plugin_body

    draft = upsert_draft_content({}, spec.id, preset.id, '{"continueOnRestart": false}')
    name, body, source = resolve_preset_body(preset, "neoforge", spec, draft)
    assert name == "config.json"
    assert source == "draft"
    assert "false" in body
    _, factory_body, factory_source = resolve_preset_body(preset, "neoforge", spec, {})
    assert factory_source == "factory"
    assert "true" in factory_body


def test_pick_install_pin_requires_matching_version():
    from app.services.minecraft_mod_tools import MinecraftModToolsError, pick_install_pin

    rows = [
        {"version_id": "aaa", "version_number": "1.4.20", "filename": "a.jar"},
        {"version_id": "bbb", "version_number": "1.4.23", "filename": "b.jar"},
    ]
    picked = pick_install_pin(rows, "bbb")
    assert picked["filename"] == "b.jar"
    with pytest.raises(MinecraftModToolsError, match="请选择模组版本"):
        pick_install_pin(rows, "")
    with pytest.raises(MinecraftModToolsError, match="不匹配"):
        pick_install_pin(rows, "zzz")


def test_catalog_includes_modrinth_project_id(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc,
        "lookup_latest_pin",
        lambda spec, loader="", mc_version="": None,
    )
    out = svc._catalog_out(
        _chunky(),
        loader="neoforge",
        mc_version="1.21.1",
        filename="Chunky-NeoForge-1.4.23.jar",
        directory="/mods",
    )
    assert out["project_id"] == "fALzjamp"


def test_list_tool_versions_filters_by_live_server(monkeypatch):
    from app.services import minecraft_mod_tools as svc

    monkeypatch.setattr(
        svc,
        "_server_context",
        lambda db: {"loader": "neoforge", "mc_version": "1.21.1"},
    )
    monkeypatch.setattr(
        svc.modrinth,
        "list_versions",
        lambda project_id, loader="", mc_version="": [
            {
                "version_id": "aaa",
                "version_number": "1.4.20",
                "filename": "a.jar",
                "download_url": "https://example/a.jar",
            }
        ],
    )
    out = svc.list_tool_versions(object(), "chunky")
    assert out["loader"] == "neoforge"
    assert out["mc_version"] == "1.21.1"
    assert out["source"] == "modrinth"
    assert out["versions"][0]["version_id"] == "aaa"
