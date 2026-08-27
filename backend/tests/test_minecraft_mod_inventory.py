"""Minecraft 模组库存指纹对账。"""

from __future__ import annotations

from app.services.minecraft.mod_inventory import (
    apply_fingerprint,
    empty_store,
    entry_matches_spec,
    hits_for_spec,
    jar_path,
    placeholder_from_disk,
    record_install,
    stamp_tool_ids,
)
from app.services.minecraft.mod_registry import SPECS


def _chunky():
    return next(spec for spec in SPECS if spec.id == "chunky")


def _bluemap():
    return next(spec for spec in SPECS if spec.id == "bluemap")


def _disk(filename: str, directory: str = "/mods", size: int = 10, mtime: str = "t1"):
    kind = "plugin" if directory == "/plugins" else "mod"
    return {
        "filename": filename,
        "directory": directory,
        "kind": kind,
        "size": size,
        "modified_at": mtime,
    }


def test_jar_path():
    assert jar_path("/mods", "a.jar") == "/mods/a.jar"
    assert jar_path("/plugins/", "b.jar") == "/plugins/b.jar"


def test_fingerprint_new_jars_are_pending():
    store, pending = apply_fingerprint(
        empty_store(),
        [_disk("Chunky-1.4.40.jar", "/plugins"), _disk("spark.jar", "/plugins")],
    )
    assert len(store["jars"]) == 2
    assert len(pending) == 2
    assert all(not row["identified"] for row in store["jars"])


def test_fingerprint_keeps_identified_same_file():
    path = jar_path("/plugins", "Chunky-1.4.40.jar")
    prev = placeholder_from_disk(
        _disk("Chunky-1.4.40.jar", "/plugins"), path=path
    )
    prev["identified"] = True
    prev["mod_ids"] = ["chunky"]
    prev["mod_version"] = "1.4.40"
    stored = {"jars": [prev], "scanned_at": "old"}
    store, pending = apply_fingerprint(
        stored, [_disk("Chunky-1.4.40.jar", "/plugins")]
    )
    assert pending == []
    assert store["jars"][0]["mod_version"] == "1.4.40"
    assert store["jars"][0]["identified"] is True


def test_fingerprint_deletes_missing_without_download():
    path = jar_path("/mods", "gone.jar")
    prev = placeholder_from_disk(_disk("gone.jar"), path=path)
    prev["identified"] = True
    store, pending = apply_fingerprint({"jars": [prev]}, [_disk("kept.jar")])
    names = {row["filename"] for row in store["jars"]}
    assert names == {"kept.jar"}
    assert len(pending) == 1
    assert pending[0]["filename"] == "kept.jar"


def test_fingerprint_size_change_requeues():
    path = jar_path("/mods", "bluemap.jar")
    prev = placeholder_from_disk(_disk("bluemap.jar", size=10), path=path)
    prev["identified"] = True
    prev["mod_ids"] = ["bluemap"]
    store, pending = apply_fingerprint(
        {"jars": [prev]}, [_disk("bluemap.jar", size=20)]
    )
    assert len(pending) == 1
    assert pending[0]["identified"] is False
    assert pending[0]["mod_ids"] == []


def test_fingerprint_failed_identify_not_retried_until_force():
    path = jar_path("/mods", "bad.jar")
    prev = placeholder_from_disk(_disk("bad.jar"), path=path)
    prev["identify_error"] = "不是有效的 jar"
    store, pending = apply_fingerprint({"jars": [prev]}, [_disk("bad.jar")])
    assert pending == []
    assert store["jars"][0]["identify_error"] == "不是有效的 jar"
    _, forced = apply_fingerprint({"jars": [prev]}, [_disk("bad.jar")], force=True)
    assert len(forced) == 1
    assert forced[0]["identify_error"] == ""


def test_entry_matches_spec_by_mod_id_not_filename():
    spec = _chunky()
    helper = {
        "filename": "ChunkyHelper.jar",
        "mod_ids": ["chunkyhelper"],
        "mod_names": ["Chunky Helper"],
        "identified": True,
        "project_id": "",
    }
    assert entry_matches_spec(helper, spec) is False
    real = {
        "filename": "something-odd.jar",
        "mod_ids": ["chunky"],
        "identified": True,
        "project_id": "",
    }
    assert entry_matches_spec(real, spec) is True


def test_entry_matches_spec_filename_fallback_when_unidentified():
    spec = _bluemap()
    row = {
        "filename": "bluemap-5.12-neoforge.jar",
        "identified": False,
        "mod_ids": [],
        "project_id": "",
    }
    assert entry_matches_spec(row, spec) is True
    row["identified"] = True
    assert entry_matches_spec(row, spec) is False


def test_stamp_clears_stale_tool_id_after_identify():
    store = stamp_tool_ids(
        {
            "jars": [
                {
                    "filename": "ChunkyHelper.jar",
                    "identified": True,
                    "mod_ids": ["chunkyhelper"],
                    "tool_id": "chunky",
                    "project_id": "",
                }
            ]
        }
    )
    assert store["jars"][0]["tool_id"] == ""


def test_hits_for_spec_uses_inventory():
    jars = stamp_tool_ids(
        {
            "jars": [
                {
                    "path": "/mods/bluemap.jar",
                    "filename": "bluemap.jar",
                    "directory": "/mods",
                    "kind": "mod",
                    "identified": True,
                    "mod_ids": ["bluemap"],
                    "mod_version": "5.23",
                    "project_id": "swbUV1cr",
                }
            ]
        }
    )["jars"]
    hits = hits_for_spec(jars, _bluemap())
    assert hits[0]["mod_version"] == "5.23"
    assert hits_for_spec(jars, _chunky()) == []


def test_versions_from_hashes_empty_and_404(monkeypatch):
    from app.services.minecraft import modrinth as modrinth

    assert modrinth.versions_from_hashes([]) == {}

    class _Resp:
        status_code = 404

        def json(self):
            return {}

    monkeypatch.setattr(modrinth, "http_request", lambda *a, **k: _Resp())
    assert modrinth.versions_from_hashes(["abc"]) == {}


def test_record_install_skips_non_session():
    record_install(
        object(),
        spec=_bluemap(),
        directory="/mods",
        filename="bluemap.jar",
        pin={"version_number": "5.23"},
        removed_hits=[],
    )
