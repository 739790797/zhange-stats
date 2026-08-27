"""Minecraft 模组键值预设：解析 / 打补丁 / 对账。"""

from __future__ import annotations

import json

from app.services.minecraft.config_pins import (
    apply_scalar_pins,
    normalize_directories,
    parse_scalar_keys,
    path_is_within,
    pin_directories,
    read_saved_directories,
    read_saved_pins,
    reconcile_pins,
    safe_server_file_path,
    write_saved_entry,
    write_saved_pins,
)


def test_parse_and_patch_properties_keeps_comments():
    text = "# motd\nmotd=old\nmax-players=10\n"
    parsed = parse_scalar_keys(text, "server.properties")
    assert parsed["motd"] == "old"
    patched = apply_scalar_pins(text, "server.properties", {"motd": "hello"})
    assert patched.splitlines()[0] == "# motd"
    assert "motd=hello" in patched
    assert "max-players=10" in patched


def test_parse_json_top_level_scalars_skips_nested():
    text = json.dumps(
        {
            "language": "en_US",
            "continueOnRestart": False,
            "updateInterval": 5,
            "nested": {"x": 1},
            "list": [1],
        }
    )
    parsed = parse_scalar_keys(text, "config.json")
    assert parsed == {
        "language": "en_US",
        "continueOnRestart": "false",
        "updateInterval": "5",
    }
    patched = apply_scalar_pins(
        text,
        "config.json",
        {"continueOnRestart": "true", "language": "zh_CN"},
    )
    data = json.loads(patched)
    assert data["continueOnRestart"] is True
    assert data["language"] == "zh_CN"
    assert data["nested"] == {"x": 1}


def test_conf_line_replace_keeps_comments():
    text = (
        "# BlueMap core\n"
        "accept-download: false\n"
        "render-thread-count: 2\n"
        "webapp {\n"
        "  enabled: true\n"
        "}\n"
    )
    parsed = parse_scalar_keys(text, "core.conf")
    assert parsed["accept-download"] == "false"
    assert parsed["render-thread-count"] == "2"
    assert "enabled" not in parsed
    patched = apply_scalar_pins(text, "core.conf", {"accept-download": "true"})
    assert "# BlueMap core" in patched
    assert "accept-download: true" in patched
    assert "  enabled: true" in patched


def test_legacy_blob_counts_as_no_pins():
    blob = {
        "chunky": {
            "zhange": {"content": '{"a":1}', "filename": "config.json"},
        }
    }
    assert read_saved_pins(blob, "chunky") == []
    assert read_saved_pins("nope", "chunky") == []
    written = write_saved_pins(
        blob,
        "bluemap",
        [
            {
                "file": "/config/bluemap/core.conf",
                "key": "accept-download",
                "value": "true",
            }
        ],
    )
    assert read_saved_pins(written, "bluemap")[0]["file"] == "/config/bluemap/core.conf"
    assert "chunky" in written


def test_rejects_parent_path_and_unknown_ext():
    written = write_saved_pins(
        {},
        "bluemap",
        [
            {"file": "../secret.conf", "key": "a", "value": "1"},
            {"file": "/config/../secret.conf", "key": "a", "value": "1"},
            {
                "file": "/config/bluemap/core.conf",
                "key": "accept-download",
                "value": "true",
            },
            {"file": "/mods/mod.jar", "key": "a", "value": "1"},
        ],
    )
    pins = read_saved_pins(written, "bluemap")
    assert pins == [
        {
            "file": "/config/bluemap/core.conf",
            "key": "accept-download",
            "value": "true",
        }
    ]
    cleared = write_saved_pins(written, "bluemap", [])
    assert read_saved_pins(cleared, "bluemap") == []
    assert "bluemap" not in cleared


def test_safe_server_file_path_and_directories():
    assert safe_server_file_path("config/chunky/config.json") == "/config/chunky/config.json"
    assert safe_server_file_path("/config/../secret.conf") == ""
    assert safe_server_file_path("") == ""
    assert normalize_directories(["/", "/config/chunky", "../x", "/config/chunky"]) == [
        "/config/chunky"
    ]
    assert path_is_within("/config/chunky/config.json", "/config/chunky")
    assert not path_is_within("/config/other.json", "/config/chunky")
    pins = [
        {"file": "/config/chunky/config.json", "key": "language", "value": "zh_CN"},
        {"file": "/plugins/Chunky/config.yml", "key": "language", "value": "zh_CN"},
        {"file": "/config/chunky/tasks.json", "key": "forceLoad", "value": "true"},
    ]
    assert pin_directories(pins) == ["/config/chunky", "/plugins/Chunky"]


def test_user_directories_kept_when_saving_pins():
    blob = write_saved_entry(
        {},
        "chunky",
        directories=["/config/chunky", "/plugins/Chunky"],
    )
    assert read_saved_directories(blob, "chunky") == [
        "/config/chunky",
        "/plugins/Chunky",
    ]
    blob = write_saved_pins(
        blob,
        "chunky",
        [
            {
                "file": "/config/chunky/config.json",
                "key": "language",
                "value": "zh_CN",
            },
            {"file": "/config.json", "key": "a", "value": "1"},
        ],
    )
    assert read_saved_directories(blob, "chunky") == [
        "/config/chunky",
        "/plugins/Chunky",
    ]
    assert [row["file"] for row in read_saved_pins(blob, "chunky")] == [
        "/config/chunky/config.json"
    ]
    kept = write_saved_pins(blob, "chunky", [])
    assert read_saved_directories(kept, "chunky") == [
        "/config/chunky",
        "/plugins/Chunky",
    ]
    assert read_saved_pins(kept, "chunky") == []
    cleared = write_saved_entry(blob, "chunky", directories=[])
    assert "chunky" not in cleared


def test_reconcile_three_states():
    pins = [
        {
            "file": "/config/bluemap/core.conf",
            "key": "accept-download",
            "value": "true",
        },
    ]
    missing = reconcile_pins(pins=pins, files={})
    assert missing["status"] == "missing_files"

    empty = reconcile_pins(
        pins=[], files={"/config/bluemap/core.conf": "a: 1\n"}
    )
    assert empty["status"] == "no_preset"

    mismatch = reconcile_pins(
        pins=pins,
        files={"/config/bluemap/core.conf": "accept-download: false\n"},
    )
    assert mismatch["status"] == "mismatch"
    assert mismatch["diffs"][0]["actual"] == "false"

    match = reconcile_pins(
        pins=pins,
        files={"/config/bluemap/core.conf": "accept-download: true\n"},
    )
    assert match["status"] == "match"

    gone = reconcile_pins(
        pins=pins, files={"/config/bluemap/core.conf": None}
    )
    assert gone["status"] == "missing_files"
    assert gone["missing_files"] == ["/config/bluemap/core.conf"]

    mixed = reconcile_pins(
        pins=[
            {"file": "/config/a.conf", "key": "x", "value": "1"},
            {"file": "/plugins/b.yml", "key": "y", "value": "2"},
        ],
        files={
            "/config/a.conf": "x: 1\n",
            "/plugins/b.yml": None,
        },
    )
    assert mixed["status"] == "mismatch"
    assert mixed["missing_files"] == ["/plugins/b.yml"]
