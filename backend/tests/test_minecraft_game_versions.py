"""Minecraft game version catalog (Mojang manifest, Fabric fallback)."""

from app.services import minecraft_profile as profile_svc


def test_mojang_manifest_maps_type_and_release_time(monkeypatch):
    def fake_http(url, **kwargs):
        assert "piston-meta" in url
        return {
            "latest": {"release": "1.21.1", "snapshot": "24w36a"},
            "versions": [
                {
                    "id": "24w36a",
                    "type": "snapshot",
                    "releaseTime": "2024-09-04T12:00:00+00:00",
                },
                {
                    "id": "1.21.1",
                    "type": "release",
                    "releaseTime": "2024-08-08T12:26:46+00:00",
                },
                {
                    "id": "a1.1.2_01",
                    "type": "old_alpha",
                    "releaseTime": "2010-09-13T00:00:00+00:00",
                },
            ],
        }

    monkeypatch.setattr(profile_svc, "_http_json", fake_http)
    rows = profile_svc.list_game_versions()
    assert [r["version"] for r in rows] == ["24w36a", "1.21.1", "a1.1.2_01"]
    assert rows[0]["stable"] is False
    assert rows[0]["version_type"] == "snapshot"
    assert rows[1]["stable"] is True
    assert rows[1]["version_type"] == "release"
    assert rows[1]["release_time"] == "2024-08-08T12:26:46+00:00"
    assert rows[2]["version_type"] == "old_alpha"


def test_falls_back_to_fabric_when_mojang_fails(monkeypatch):
    def fake_http(url, **kwargs):
        if "piston-meta" in url:
            raise profile_svc.MinecraftProfileError("down", status_code=502)
        assert "fabricmc" in url
        return [{"version": "1.21.1", "stable": True}, {"version": "24w36a", "stable": False}]

    monkeypatch.setattr(profile_svc, "_http_json", fake_http)
    rows = profile_svc.list_game_versions()
    assert rows[0] == {
        "version": "1.21.1",
        "stable": True,
        "version_type": "release",
        "release_time": None,
    }
    assert rows[1]["version_type"] == "snapshot"
