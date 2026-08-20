"""Minecraft pack / properties / status helpers."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO

from app.services.minecraft_pack import (
    build_mrpack_bytes,
    merge_properties,
    parse_properties,
)
from app.services.minecraft_status import (
    flatten_chat,
    flatten_legacy_motd,
    pack_varint,
    parse_status_json,
    sanitize_favicon,
    strip_section_codes,
)
from app.services.pelican_client import (
    friendly_error,
    normalize_pelican_base_url,
    pelican_configured,
)


def test_merge_properties_updates_and_appends():
    text = "motd=old\nmax-players=10\n"
    merged = merge_properties(text, {"motd": "hello", "pvp": "true"})
    props = parse_properties(merged)
    assert props["motd"] == "hello"
    assert props["max-players"] == "10"
    assert props["pvp"] == "true"


def test_parse_skips_comments():
    text = "# comment\nmotd=hi\n"
    assert parse_properties(text) == {"motd": "hi"}


def test_mrpack_skips_client_only_and_embeds_overrides():
    blob = build_mrpack_bytes(
        mc_version="1.21.1",
        loader="fabric",
        loader_version="0.16.9",
        mods=[
            {
                "filename": "ok.jar",
                "download_url": "https://cdn.example/ok.jar",
                "sha512": "abc",
                "file_size": 10,
                "env_server": "required",
            },
            {
                "filename": "client.jar",
                "download_url": "https://cdn.example/client.jar",
                "sha512": "def",
                "env_server": "unsupported",
            },
        ],
        overrides={"server.properties": "motd=zhange\n", "config/foo.toml": "a = 1\n"},
    )
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        index = json.loads(zf.read("modrinth.index.json"))
        assert index["dependencies"]["minecraft"] == "1.21.1"
        assert index["dependencies"]["fabric-loader"] == "0.16.9"
        assert [f["path"] for f in index["files"]] == ["mods/ok.jar"]
        assert zf.read("server-overrides/server.properties").decode() == "motd=zhange\n"
        assert "server-overrides/config/foo.toml" in zf.namelist()


def test_flatten_motd_and_section_codes():
    chat = {"text": "A", "extra": [{"text": "B"}, "C"]}
    assert flatten_chat(chat) == "ABC"
    assert strip_section_codes("§aHello §lWorld") == "Hello World"


def test_flatten_legacy_motd_named_and_hex_color():
    chat = {
        "text": "A",
        "extra": [
            {"text": "B", "color": "gold", "bold": True},
            {"text": "C", "color": "#55ff55"},
        ],
    }
    raw = flatten_legacy_motd(chat)
    assert raw.startswith("A")
    assert "§6" in raw and "§l" in raw and "B" in raw
    assert "§x§5§5§f§f§5§5" in raw
    assert strip_section_codes(raw) == "ABC"


def test_parse_status_json_players():
    parsed = parse_status_json(
        {
            "description": {"text": "§ahi"},
            "version": {"name": "1.21.1"},
            "favicon": "data:image/png;base64,iVBORw0KGgo=",
            "players": {
                "online": 1,
                "max": 8,
                "sample": [{"name": "Steve", "id": "abc"}],
            },
        }
    )
    assert parsed["motd"] == "hi"
    assert parsed["motd_raw"] == "§ahi"
    assert parsed["favicon"].startswith("data:image/png;base64,")
    assert parsed["players_online"] == 1
    assert parsed["players"][0]["name"] == "Steve"


def test_sanitize_favicon_rejects_non_png_and_oversize():
    assert sanitize_favicon("javascript:alert(1)") == ""
    assert sanitize_favicon("data:image/gif;base64,AAAA") == ""
    assert sanitize_favicon("iVBORw" + "A" * 10) == "data:image/png;base64,iVBORw" + "A" * 10
    assert sanitize_favicon("iVBORw" + "A" * 96_001) == ""


def test_pack_varint_roundtrip_small():
    assert pack_varint(0) == b"\x00"
    assert pack_varint(1) == b"\x01"
    assert pack_varint(128) == b"\x80\x01"


def test_pelican_base_url_strips_api_suffix():
    assert (
        normalize_pelican_base_url("https://panel.example.com/api/client/")
        == "https://panel.example.com"
    )
    assert not pelican_configured("", "tok", "uuid")
    assert pelican_configured("https://p.example", "tok", "abcd")


def test_pelican_friendly_error_application_key():
    msg = friendly_error(
        403,
        "You are attempting to use an application API key on an endpoint that requires a client API key.",
    )
    assert "Application API Key" in msg
    assert "Client API Key" in msg
