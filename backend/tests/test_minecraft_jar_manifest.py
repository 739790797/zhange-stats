"""Minecraft jar 元数据解析。"""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from app.services.minecraft.jar_manifest import (
    JarManifestError,
    parse_jar_bytes,
    verify_jar_archive,
    verify_sha512,
)


def _jar(**files: str | bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in files.items():
            data = body.encode("utf-8") if isinstance(body, str) else body
            zf.writestr(name, data)
    return buf.getvalue()


def test_parse_fabric_mod_json():
    data = _jar(
        **{
            "fabric.mod.json": '{"id":"bluemap","name":"BlueMap","version":"5.23"}',
        }
    )
    parsed = parse_jar_bytes(data)
    assert parsed["mod_ids"] == ["bluemap"]
    assert parsed["mod_names"] == ["BlueMap"]
    assert parsed["mod_version"] == "5.23"


def test_parse_mods_toml_and_placeholder_version_uses_manifest():
    data = _jar(
        **{
            "META-INF/mods.toml": (
                'modLoader="javafml"\n'
                "[[mods]]\n"
                'modId="bluemap"\n'
                'version="${file.jarVersion}"\n'
                'displayName="BlueMap"\n'
            ),
            "META-INF/MANIFEST.MF": "Manifest-Version: 1.0\nImplementation-Version: 5.23\n",
        }
    )
    parsed = parse_jar_bytes(data)
    assert parsed["mod_ids"] == ["bluemap"]
    assert parsed["mod_names"] == ["BlueMap"]
    assert parsed["mod_version"] == "5.23"


def test_parse_plugin_yml():
    data = _jar( **{"plugin.yml": "name: Chunky\nversion: 1.4.40\nmain: example.Main\n"})
    parsed = parse_jar_bytes(data)
    assert parsed["mod_ids"] == ["Chunky"]
    assert parsed["mod_names"] == ["Chunky"]
    assert parsed["mod_version"] == "1.4.40"


def test_parse_empty_metadata():
    data = _jar(**{"readme.txt": "no metadata"})
    parsed = parse_jar_bytes(data)
    assert parsed["mod_ids"] == []
    assert parsed["mod_version"] == ""


def test_parse_corrupt_zip():
    with pytest.raises(JarManifestError):
        parse_jar_bytes(b"not-a-jar")


def test_verify_sha512_compares_hex_case_insensitively():
    data = b"jar-bytes"
    verify_sha512(data, hashlib.sha512(data).hexdigest().upper())
    with pytest.raises(JarManifestError):
        verify_sha512(data, hashlib.sha512(b"other").hexdigest())
    with pytest.raises(JarManifestError):
        verify_sha512(data, "")


def test_verify_jar_archive_accepts_complete_bootable_jar():
    verify_jar_archive(_jar(**{"META-INF/MANIFEST.MF": "Main-Class: a.B\n", "a/B.class": b"\xca\xfe"}))
    verify_jar_archive(_jar(**{"fabric.mod.json": "{}"}), require_manifest=False)


def test_verify_jar_archive_rejects_error_pages_truncation_and_bad_crc():
    good = _jar(**{"META-INF/MANIFEST.MF": "Main-Class: a.B\n", "payload.bin": b"A" * 200})
    with pytest.raises(JarManifestError):
        verify_jar_archive(b"<html>502 Bad Gateway</html>")
    with pytest.raises(JarManifestError):
        verify_jar_archive(good[: len(good) // 2])
    with pytest.raises(JarManifestError, match="payload.bin"):
        verify_jar_archive(good.replace(b"A" * 200, b"A" * 199 + b"B"))
    with pytest.raises(JarManifestError, match="MANIFEST"):
        verify_jar_archive(_jar(**{"fabric.mod.json": "{}"}))
    with pytest.raises(JarManifestError, match="过大"):
        verify_jar_archive(good, max_uncompressed=100)
