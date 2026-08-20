"""Minecraft playbook snapshot vs draft."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.minecraft_profile import (
    desired_snapshot,
    is_playbook_dirty,
    playbook_from_snapshot,
    public_applied_view,
    seed_applied_if_missing,
)


def _row(**kwargs):
    defaults = {
        "mc_version": "1.21.1",
        "loader": "fabric",
        "loader_version": "0.16.9",
        "mods_json": [
            {
                "project_id": "p1",
                "project_title": "Lithium",
                "filename": "lithium.jar",
                "version_number": "0.1",
                "download_url": "https://cdn.example/lithium.jar",
                "sha512": "abc",
            }
        ],
        "overrides_json": {"server.properties": "motd=hello\nmax-players=20\n"},
        "public_host": "zhange.space",
        "public_port": 25565,
        "applied_json": None,
        "last_applied_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_never_applied_is_not_dirty():
    row = _row()
    assert not is_playbook_dirty(row)
    assert public_applied_view(row) is None


def test_matching_snapshot_is_clean():
    row = _row()
    row.applied_json = desired_snapshot(row)
    assert not is_playbook_dirty(row)


def test_old_applied_snapshot_with_rcon_keys_is_clean():
    row = _row()
    snap = desired_snapshot(row)
    snap["rcon_enabled"] = True
    snap["rcon_port"] = 25575
    snap["rcon_connect_host"] = "127.0.0.1"
    snap["rcon_connect_port"] = 0
    snap["rcon_password_set"] = True
    row.applied_json = snap
    assert not is_playbook_dirty(row)


def test_draft_change_marks_dirty_and_public_view_stays_on_applied():
    row = _row()
    row.applied_json = desired_snapshot(row)
    row.mc_version = "1.21.4"
    row.mods_json = []
    assert is_playbook_dirty(row)
    public = public_applied_view(row)
    assert public is not None
    assert public["mc_version"] == "1.21.1"
    assert public["mods"][0]["project_title"] == "Lithium"
    assert "download_url" not in public["mods"][0]
    assert public["properties"]["motd"] == "hello"


def test_seed_applied_only_when_last_applied_without_snapshot():
    row = _row(last_applied_at="2026-08-20T00:00:00")
    assert seed_applied_if_missing(row) is True
    assert row.applied_json["mc_version"] == "1.21.1"
    assert seed_applied_if_missing(row) is False
    row.mc_version = "1.21.4"
    assert seed_applied_if_missing(row) is False
    assert row.applied_json["mc_version"] == "1.21.1"


def test_playbook_from_snapshot_splits_properties():
    row = _row()
    playbook = playbook_from_snapshot(desired_snapshot(row))
    assert playbook is not None
    assert playbook["properties"]["max-players"] == "20"
    assert playbook["mods"][0]["filename"] == "lithium.jar"
