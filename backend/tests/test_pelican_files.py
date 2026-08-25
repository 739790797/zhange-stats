"""Pelican 远程路径与文件对象解析。"""

from __future__ import annotations

import pytest

from app.services.minecraft.files import normalize_mode
from app.services.minecraft.pelican import (
    PelicanError,
    join_remote_path,
    normalize_remote_directory,
    normalize_remote_file_path,
    normalize_rename_target,
    parse_file_object,
    sanitize_filename,
    split_remote_path,
)


def test_normalize_directory_strips_dots_and_slashes():
    assert normalize_remote_directory("") == "/"
    assert normalize_remote_directory("mods") == "/mods"
    assert normalize_remote_directory("/mods/./config/") == "/mods/config"
    assert normalize_remote_directory("/a//b") == "/a/b"


def test_normalize_directory_rejects_parent():
    with pytest.raises(PelicanError):
        normalize_remote_directory("/mods/../secret")


def test_file_path_and_join():
    assert normalize_remote_file_path("zhange/boot.sh") == "/zhange/boot.sh"
    assert split_remote_path("/mods/lithium.jar") == ("/mods", "lithium.jar")
    assert join_remote_path("/mods", "a.jar") == "/mods/a.jar"
    assert join_remote_path("/", "eula.txt") == "/eula.txt"
    with pytest.raises(PelicanError):
        normalize_remote_file_path("/")
    with pytest.raises(PelicanError):
        sanitize_filename("../x")
    with pytest.raises(PelicanError):
        sanitize_filename("a/b")
    assert sanitize_filename("C:/tmp/eula.txt", allow_path=True) == "eula.txt"


def test_rename_target_allows_relative_move():
    assert normalize_rename_target("new.txt") == "new.txt"
    assert normalize_rename_target("/mods/moved.jar") == "mods/moved.jar"
    with pytest.raises(PelicanError):
        normalize_rename_target("../etc/passwd")


def test_parse_file_object_client_shape():
    parsed = parse_file_object(
        {
            "object": "file_object",
            "attributes": {
                "name": "server.properties",
                "is_file": True,
                "is_symlink": False,
                "size": 12,
                "mode": "-rw-r--r--",
                "mode_bits": "0644",
                "mimetype": "text/plain",
                "modified_at": "2026-08-21T00:00:00+00:00",
            },
        }
    )
    assert parsed is not None
    assert parsed["name"] == "server.properties"
    assert parsed["is_file"] is True
    assert parsed["size"] == 12
    assert parsed["mimetype"] == "text/plain"


def test_parse_file_object_wings_file_flag():
    parsed = parse_file_object({"name": "config", "file": False, "size": 0})
    assert parsed is not None
    assert parsed["is_file"] is False


def test_chmod_mode():
    from app.services.minecraft.files import MinecraftFilesError

    assert normalize_mode("644") == "644"
    assert normalize_mode("0755") == "0755"
    with pytest.raises(MinecraftFilesError):
        normalize_mode("rwx")


def test_list_files_parses_collection(monkeypatch):
    from app.services.minecraft.pelican import list_files

    captured: dict[str, str] = {}

    def fake_request(method, url, token, **kwargs):
        captured["url"] = url
        return {
            "data": [
                {"attributes": {"name": "config", "is_file": False, "size": 0}},
                {"attributes": {"name": "eula.txt", "is_file": True, "size": 4}},
            ]
        }

    monkeypatch.setattr("app.services.minecraft.pelican._request", fake_request)
    rows = list_files("https://p.example", "tok", "abcd", "mods")
    assert [r["name"] for r in rows] == ["config", "eula.txt"]
    assert "directory=%2Fmods" in captured["url"]


def test_get_file_contents_keeps_json_text(monkeypatch):
    from app.services.minecraft.pelican import get_file_contents

    def fake_request(method, url, token, **kwargs):
        assert kwargs.get("decode") == "text"
        return '{"motd":"hi"}'

    monkeypatch.setattr("app.services.minecraft.pelican._request", fake_request)
    text = get_file_contents("https://p.example", "tok", "abcd", "server.properties")
    assert text == '{"motd":"hi"}'
