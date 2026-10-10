"""Pelican 远程路径与文件对象解析。"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from app.services.minecraft import pelican
from app.services.minecraft.files import normalize_mode
from app.services.minecraft.pelican import (
    PelicanError,
    is_absent_file_error,
    join_remote_path,
    normalize_remote_directory,
    normalize_remote_file_path,
    normalize_rename_target,
    parse_file_object,
    pelican_browser_status,
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


def test_pelican_browser_status_hides_panel_auth_from_the_site_session():
    assert pelican_browser_status(401) == 502
    assert pelican_browser_status(403) == 502
    assert pelican_browser_status(404) == 404
    assert pelican_browser_status(400) == 400
    assert pelican_browser_status(500) == 500
    assert pelican_browser_status(None) == 502


def test_wings_generic_500_counts_as_absent_file():
    assert is_absent_file_error(PelicanError("Pelican HTTP 500", status_code=500))
    assert is_absent_file_error(PelicanError("missing", status_code=404))
    assert is_absent_file_error(PelicanError("bad path", status_code=400))
    assert not is_absent_file_error(PelicanError("unauthorized", status_code=401))


class _StreamResp:
    def __init__(self, chunks: list[bytes], *, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks
        self.pulled = 0

    def iter_bytes(self):
        for chunk in self._chunks:
            self.pulled += 1
            yield chunk


def _serve(monkeypatch, resp: _StreamResp) -> None:
    @contextmanager
    def fake_stream(method, url, **_kwargs):
        assert (method, url) == ("GET", "https://signed")
        yield resp

    monkeypatch.setattr(pelican, "get_download_url", lambda *_a: "https://signed")
    monkeypatch.setattr(pelican, "http_stream", fake_stream)


def test_download_file_stops_reading_past_the_cap(monkeypatch):
    resp = _StreamResp([b"x" * 4] * 50)
    _serve(monkeypatch, resp)
    with pytest.raises(PelicanError, match="过大"):
        pelican.download_file("https://p", "tok", "uuid", "/mods/a.jar", max_bytes=10)
    assert resp.pulled == 3


def test_download_file_rejects_declared_size_before_reading(monkeypatch):
    resp = _StreamResp([b"x"], headers={"content-length": "11"})
    _serve(monkeypatch, resp)
    with pytest.raises(PelicanError, match="过大"):
        pelican.download_file("https://p", "tok", "uuid", "/mods/a.jar", max_bytes=10)
    assert resp.pulled == 0


def test_download_file_returns_body_and_maps_errors(monkeypatch):
    _serve(monkeypatch, _StreamResp([b"ab", b"cd"], headers={"content-length": "4"}))
    assert pelican.download_file("https://p", "tok", "uuid", "/mods/a.jar", max_bytes=4) == b"abcd"
    _serve(monkeypatch, _StreamResp([b"nope" * 200], status_code=404))
    with pytest.raises(PelicanError) as missing:
        pelican.download_file("https://p", "tok", "uuid", "/mods/a.jar", max_bytes=4)
    assert missing.value.status_code == 404


class _FakePanel:
    """内存里的服文件：记录 pull / 下载 / 删 / 改名的顺序。"""

    def __init__(self, monkeypatch, files: dict[str, bytes], served: bytes):
        self.files = dict(files)
        self.served = served
        self.calls: list[tuple[str, ...]] = []
        for name in ("pull_file", "download_file", "list_files", "delete_files", "rename_files"):
            monkeypatch.setattr(pelican, name, getattr(self, name))

    def pull_file(self, _base, _token, _uuid, *, url, directory, filename, timeout=0):
        path = join_remote_path(directory, filename)
        self.calls.append(("pull", path))
        self.files[path] = self.served

    def download_file(self, _base, _token, _uuid, path, *, max_bytes, timeout=0):
        self.calls.append(("download", path))
        return self.files[path]

    def list_files(self, _base, _token, _uuid, directory):
        return [
            {"name": split_remote_path(path)[1]}
            for path in self.files
            if split_remote_path(path)[0] == normalize_remote_directory(directory)
        ]

    def delete_files(self, _base, _token, _uuid, *, root, files):
        for name in files:
            path = join_remote_path(root, name)
            self.calls.append(("delete", path))
            self.files.pop(path, None)

    def rename_files(self, _base, _token, _uuid, *, root, files):
        for src, dest in files:
            self.calls.append(("rename", join_remote_path(root, src), join_remote_path(root, dest)))
            self.files[join_remote_path(root, dest)] = self.files.pop(join_remote_path(root, src))


def _reject_unless(expected: bytes):
    def verify(data: bytes) -> None:
        if data != expected:
            raise PelicanError("校验不通过")

    return verify


def test_pull_file_verified_replaces_same_name_only_after_check(monkeypatch):
    panel = _FakePanel(monkeypatch, {"/mods/a.jar": b"old"}, served=b"new")
    path = pelican.pull_file_verified(
        "https://p", "tok", "uuid",
        url="https://cdn/a.jar", directory="mods", filename="a.jar",
        verify=_reject_unless(b"new"), max_bytes=100,
    )
    temp = f"/mods/a.jar{pelican.PULL_TEMP_SUFFIX}"
    assert path == "/mods/a.jar"
    assert panel.files == {"/mods/a.jar": b"new"}
    assert panel.calls == [
        ("pull", temp),
        ("download", temp),
        ("delete", "/mods/a.jar"),
        ("rename", temp, "/mods/a.jar"),
    ]


def test_pull_file_verified_failure_discards_temp_and_keeps_original(monkeypatch):
    panel = _FakePanel(monkeypatch, {"/mods/a.jar": b"old"}, served=b"tampered")
    with pytest.raises(PelicanError, match="校验"):
        pelican.pull_file_verified(
            "https://p", "tok", "uuid",
            url="https://cdn/a.jar", directory="/mods", filename="a.jar",
            verify=_reject_unless(b"new"), max_bytes=100,
        )
    assert panel.files == {"/mods/a.jar": b"old"}
    assert [call[0] for call in panel.calls] == ["pull", "download", "delete"]
    assert panel.calls[-1] == ("delete", f"/mods/a.jar{pelican.PULL_TEMP_SUFFIX}")
