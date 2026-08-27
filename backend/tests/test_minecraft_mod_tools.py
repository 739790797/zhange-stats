"""Minecraft 模组探测 / Chunky 指令白名单。"""

from __future__ import annotations

import pytest

from app.services.minecraft.mod_registry import (
    SPECS,
    assemble_mod_command,
    command_tree_out,
    config_directory,
    config_directory_abs,
    curseforge_url,
    features_out,
    install_directory,
    jar_matches_spec,
    spec_links_out,
    version_from_jar,
)
from app.services.minecraft.mod_tools import (
    build_chunky_commands,
    is_unknown_command,
    parse_bluemap_maps,
    parse_bluemap_state,
    parse_chunky_state,
)


def _chunky():
    return next(spec for spec in SPECS if spec.id == "chunky")


def _bluemap():
    return next(spec for spec in SPECS if spec.id == "bluemap")


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


def test_assemble_bluemap_command_tree():
    spec = _bluemap()
    assert assemble_mod_command(spec, "status") == "bluemap"
    assert assemble_mod_command(spec, "start") == "bluemap start"
    assert assemble_mod_command(spec, "reload", {"mode": "light"}) == "bluemap reload light"
    assert assemble_mod_command(spec, "freeze", {"map": "world_nether"}) == (
        "bluemap freeze world_nether"
    )
    assert assemble_mod_command(spec, "update", {"map": "world"}) == "bluemap update world"
    assert assemble_mod_command(
        spec, "force-update", {"map": "world", "x": 0, "z": 64, "radius": 500}
    ) == "bluemap force-update world 0 64 500"
    assert assemble_mod_command(spec, "tasks-cancel", {"target": "all"}) == (
        "bluemap tasks cancel all"
    )
    tree_ids = [row["id"] for row in command_tree_out(spec)]
    assert "status" in tree_ids
    assert "force-update" in tree_ids
    assert "commands" in spec.capabilities
    features = features_out(spec)
    assert features[0]["id"] == "bluemap.render"
    assert features_out(_chunky())[0]["id"] == "chunky.pregenerate"


def test_assemble_bluemap_rejects_partial_update_range():
    spec = _bluemap()
    with pytest.raises(Exception, match="前面的参数"):
        assemble_mod_command(spec, "update", {"radius": 500})
    with pytest.raises(Exception, match="地图"):
        assemble_mod_command(spec, "freeze", {})
    with pytest.raises(Exception, match="地图"):
        assemble_mod_command(spec, "purge", {"map": "world; stop"})


def test_parse_bluemap_state_running():
    raw = (
        "Status\n"
        "4 render-threads are running\n"
        "map world is currently being updated\n"
        "progress: 12.345%\n"
        "remaining time: 5 minutes\n"
        "2 maps are updated\n"
        "1 maps are frozen\n"
    )
    parsed = parse_bluemap_state(raw)
    assert parsed["state"] == "running"
    assert parsed["threads"] == 4
    assert parsed["percent"] == 12.345
    assert parsed["eta"] == "5 minutes"
    assert parsed["current_map"] == "world"
    assert parsed["current_task"] == "updated"


def test_parse_bluemap_idle_stopped_paused():
    assert parse_bluemap_state("render-threads are idle")["state"] == "idle"
    assert parse_bluemap_state("render-threads are stopped")["state"] == "stopped"
    assert parse_bluemap_state("render-threads are paused")["state"] == "paused"


def test_parse_bluemap_maps_and_frozen():
    raw = "Maps\nworld\nworld_nether\nworld_the_end\nis frozen\n"
    listed = parse_bluemap_maps(raw)
    assert listed["maps"] == ["world", "world_nether", "world_the_end"]
    assert listed["frozen_maps"] == ["world_the_end"]


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
    from app.services.minecraft import mod_tools as svc

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
    assert chunky["summary"]
    spark = next(row for row in data["inventory"]["jars"] if row["filename"] == "spark.jar")
    assert spark["tool_id"] == ""
    assert spark["identified"] is False
    assert data["reconcile"]["running"] is False


def test_collect_ignores_unrelated_jars(monkeypatch):
    from app.services.minecraft import mod_tools as svc

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
    lithium = next(row for row in data["inventory"]["jars"] if "lithium" in row["filename"])
    assert lithium["tool_id"] == ""
    assert lithium["identified"] is False


def test_mc_version_skips_latest_placeholder():
    from app.services.minecraft.mod_tools import _mc_version_from_variables

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
    from app.services.minecraft.mod_tools import _infer_runtime_loader

    assert _infer_runtime_loader("java -jar neoforge-21.1.jar") == "neoforge"
    assert _infer_runtime_loader("paper-1.21.1.jar") == "paper"
    assert _infer_runtime_loader("purpur-1.21.1.jar") == "purpur"


def test_catalog_same_version_is_not_update_even_if_filename_differs(monkeypatch):
    from app.services.minecraft import mod_tools as svc

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
    from app.services.minecraft import mod_tools as svc

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
    from app.services.minecraft import mod_tools as svc

    monkeypatch.setattr(
        svc, "_live_egg_context", lambda _db: {"loader": "neoforge", "mc_version": "1.21.1"}
    )
    assert svc._server_context(object()) == {"loader": "neoforge", "mc_version": "1.21.1"}
    assert not hasattr(svc, "_applied_context")


def test_server_context_stays_empty_when_live_unknown(monkeypatch):
    from app.services.minecraft import mod_tools as svc

    monkeypatch.setattr(svc, "_live_egg_context", lambda _db: {"loader": "", "mc_version": ""})
    assert svc._server_context(object()) == {"loader": "", "mc_version": ""}


def test_live_egg_context_reads_inspect(monkeypatch):
    from app.services.minecraft import mod_tools as svc
    from app.services.minecraft import eggs as eggs
    from app.services.minecraft import pelican as pelican

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
    from app.services.minecraft import mod_tools as svc
    from app.services.minecraft import eggs as eggs
    from app.services.minecraft import pelican as pelican

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
    from app.services.minecraft import mod_tools as svc
    from app.services.minecraft import pelican as pelican

    def fake_list(_base, _token, _uuid, directory):
        if directory == "/":
            return [{"name": "libraries"}, {"name": "mods"}]
        if directory == "/libraries/net":
            return [{"name": "neoforged"}, {"name": "minecraft"}]
        return []

    monkeypatch.setattr(pelican, "list_files", fake_list)
    assert svc._live_disk_loader("https://p", "tok", "uuid") == "neoforge"


def test_factory_pins_follow_loader():
    from app.services.minecraft.mod_registry import factory_pins_out

    spec = _chunky()
    mod_pins = factory_pins_out(spec, "neoforge")
    assert {row["file"] for row in mod_pins} == {"config.json"}
    assert any(row["key"] == "continueOnRestart" and row["value"] == "true" for row in mod_pins)
    plugin_pins = factory_pins_out(spec, "paper")
    assert {row["file"] for row in plugin_pins} == {"config.yml"}
    assert any(row["key"] == "continue-on-restart" for row in plugin_pins)
    blue = factory_pins_out(_bluemap(), "neoforge")
    assert blue == [
        {"file": "core.conf", "key": "accept-download", "value": "true"}
    ]


def test_config_relpath_stays_inside_directory():
    from app.services.minecraft.mod_registry import relativize_config_path, safe_config_relpath

    assert safe_config_relpath("../secret") == ""
    assert relativize_config_path(
        "/config/chunky/tasks/config.json",
        "/config/chunky",
    ) == "tasks/config.json"
    assert relativize_config_path("config.json", "/config/chunky") == "config.json"
    assert relativize_config_path("../../server.properties", "/config/chunky") == ""
    assert relativize_config_path("/mods/foo.jar", "/config/chunky") == ""


def test_pick_install_pin_requires_matching_version():
    from app.services.minecraft.mod_tools import MinecraftModToolsError, pick_install_pin

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
    from app.services.minecraft import mod_tools as svc

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
    from app.services.minecraft import mod_tools as svc

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


@pytest.mark.parametrize(
    ("filename", "matched"),
    [
        ("bluemap-5.23-neoforge.jar", True),
        ("BlueMap-5.12-fabric.jar", True),
        ("bluemap-5.23-paper.jar", True),
        ("BlueMap-spigot.jar", True),
        ("bluemap.jar", True),
        ("BlueMap-Offline-Player-Markers-1.0.jar", False),
        ("bluemap-5.23-cli.jar", False),
        ("Chunky-NeoForge-1.4.23.jar", False),
    ],
)
def test_jar_matches_bluemap_ignores_loader(filename: str, matched: bool):
    assert jar_matches_spec(filename, _bluemap()) is matched


def test_bluemap_catalog_links_and_directories():
    spec = _bluemap()
    assert spec.links.modrinth_id == "swbUV1cr"
    assert spec.links.modrinth_slug == "bluemap"
    assert "modrinth.com/mod/bluemap" in spec_links_out(spec, "neoforge")["modrinth_url"]
    assert spec_links_out(spec, "neoforge")["icon_url"].endswith("/swbUV1cr/icon.png")
    assert curseforge_url("neoforge", spec).endswith("/mc-mods/bluemap")
    assert curseforge_url("paper", spec).endswith("/mc-mods/bluemap")
    assert version_from_jar("bluemap-5.23-neoforge.jar") == "5.23"
    assert version_from_jar("BlueMap-5.12-fabric.jar") == "5.12"
    assert version_from_jar("mod-1.4.23-beta1.jar") == "1.4.23-beta1"
    assert install_directory("neoforge", spec) == "/mods"
    assert install_directory("paper", spec) == "/plugins"
    assert config_directory("neoforge", spec) == "config/bluemap"
    assert config_directory("paper", spec) == "plugins/BlueMap"
    assert config_directory("neoforge", spec, present_directory="/plugins") == "plugins/BlueMap"
    assert config_directory_abs("neoforge", spec) == "/config/bluemap"


def test_collect_detects_bluemap_and_keeps_chunky(monkeypatch):
    from app.services.minecraft import mod_tools as svc

    monkeypatch.setattr(
        svc,
        "_scan_files",
        lambda _db, force=False: {
            "pelican_configured": True,
            "jars": [
                {
                    "filename": "bluemap-5.12-neoforge.jar",
                    "directory": "/mods",
                    "kind": "mod",
                }
            ],
            "worlds": ["world"],
            "message": "",
        },
    )
    monkeypatch.setattr(svc, "_rcon_creds", lambda _db: ("", 25575, ""))
    monkeypatch.setattr(
        svc, "_server_context", lambda _db: {"loader": "neoforge", "mc_version": "1.21.1"}
    )
    monkeypatch.setattr(svc, "lookup_latest_pin", lambda *args, **kwargs: None)
    data = svc.collect_mod_tools(object())
    ids = [row["id"] for row in data["tools"]]
    assert ids == ["chunky", "bluemap"]
    bluemap = next(row for row in data["tools"] if row["id"] == "bluemap")
    chunky = next(row for row in data["tools"] if row["id"] == "chunky")
    assert bluemap["present"] is True
    assert bluemap["filename"] == "bluemap-5.12-neoforge.jar"
    assert bluemap["links"]["modrinth_url"].endswith("/mod/bluemap")
    assert bluemap["catalog"]["installed_version"] == "5.12"
    assert bluemap["catalog"]["target_directory"] == "/mods"
    assert bluemap["config_directory"] == "/config/bluemap"
    assert "commands" in bluemap["capabilities"]
    assert bluemap["features"][0]["id"] == "bluemap.render"
    assert any(row["id"] == "status" for row in bluemap["command_tree"])
    assert chunky["present"] is False
    assert chunky["features"][0]["id"] == "chunky.pregenerate"


def test_install_never_applies_preset(monkeypatch):
    from app.services.minecraft import mod_tools as svc

    monkeypatch.setattr(
        svc,
        "_server_context",
        lambda _db: {"loader": "neoforge", "mc_version": "1.21.1"},
    )
    monkeypatch.setattr(
        svc.modrinth,
        "list_versions",
        lambda project_id, loader="", mc_version="": [
            {
                "version_id": "v1",
                "version_number": "5.23",
                "filename": "bluemap-5.23-neoforge.jar",
                "download_url": "https://example/bluemap.jar",
            }
        ],
    )
    monkeypatch.setattr(svc, "_scan_files", lambda *_a, **_k: {"jars": []})
    monkeypatch.setattr(svc, "_pelican", lambda _db: ("https://p", "tok", "uuid"))
    pulled: list[dict] = []
    monkeypatch.setattr(
        svc.pelican,
        "pull_file",
        lambda *_a, **kwargs: pulled.append(kwargs),
    )
    applied: list[str] = []
    monkeypatch.setattr(
        svc,
        "apply_tool_preset",
        lambda *_a, **_k: applied.append("hit") or {"path": "/nope", "message": "wrote"},
    )
    monkeypatch.setattr(svc, "_invalidate_scans", lambda: None)
    out = svc.install_tool(object(), "bluemap", version_id="v1", preset_id="zhange")
    assert pulled
    assert pulled[0]["filename"] == "bluemap-5.23-neoforge.jar"
    assert pulled[0]["directory"] == "/mods"
    assert applied == []
    assert out["ok"] is True
    assert out["config_path"] == ""


def test_get_tool_preset_treats_pelican_500_as_missing_file(monkeypatch):
    from app.services.minecraft import mod_tools as svc
    from app.services.minecraft.pelican import PelicanError

    monkeypatch.setattr(
        svc, "_server_context", lambda _db: {"loader": "neoforge", "mc_version": "1.21.1"}
    )
    monkeypatch.setattr(svc, "_present_directory", lambda *_a, **_k: "/mods")
    monkeypatch.setattr(svc, "_preset_blob", lambda _db: {})
    monkeypatch.setattr(
        svc.pins_svc,
        "read_saved_directories",
        lambda *_a, **_k: ["/config/chunky"],
    )
    monkeypatch.setattr(
        svc.pins_svc,
        "read_saved_pins",
        lambda *_a, **_k: [
            {
                "file": "/config/chunky/config.json",
                "key": "language",
                "value": "zh_CN",
            }
        ],
    )
    monkeypatch.setattr(svc, "_pelican", lambda _db: ("https://p", "tok", "uuid"))
    monkeypatch.setattr(svc.pelican, "list_files", lambda *_a, **_k: [])

    def boom(*_a, **_k):
        raise PelicanError(
            "Pelican HTTP 500：An unexpected error was encountered while processing this request, please try again.",
            status_code=500,
        )

    monkeypatch.setattr(svc.pelican, "get_file_contents", boom)
    out = svc.get_tool_preset(object(), "chunky")
    assert out["status"] == "missing_files"
    assert out["has_preset"] is True
    assert out["missing_files"] == ["/config/chunky/config.json"]
