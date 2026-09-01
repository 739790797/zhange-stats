"""Unit tests for Tarkov Goon Tracker parse / projection."""

from __future__ import annotations

import json

from app.services.tarkov import goon_tracker as goons


def test_normalize_goon_map_slug() -> None:
    assert goons.normalize_goon_map_slug("Customs") == "customs"
    assert goons.normalize_goon_map_slug("bigmap") == "customs"
    assert goons.normalize_goon_map_slug("factory") == ""
    assert goons.normalize_goon_map_slug("Invalid Date") == ""


def test_project_status_uses_chinese_map_name() -> None:
    status = goons.project_status(
        {
            "id": "2026-09-01T06:17:18Z|lighthouse|goon-tracker.com",
            "currentDate": "2026-09-01T06:17:18.000Z",
            "map": {"name": "Lighthouse", "slug": "lighthouse"},
        },
        "pve",
    )
    assert status["game_mode"] == "pve"
    assert status["map_slug"] == "lighthouse"
    assert status["map_name"] == "灯塔"
    assert status["map_english"] == "Lighthouse"
    assert status["seen_at"] == "2026-09-01T06:17:18Z"
    assert status["source"] == "tarkov-stammtisch"
    assert status["source_url"].endswith("/en/tarkov/goon-tracker")


def test_project_status_rejects_junk() -> None:
    status = goons.project_status(
        {
            "id": "Invalid Date",
            "currentDate": "Invalid Date",
            "map": {"slug": "alli8080-watch"},
        },
        "pvp",
    )
    assert status["map_slug"] == ""
    assert status["seen_at"] is None


def test_parse_stammtisch_bundle_picks_each_mode() -> None:
    payload = {
        "pvp": [
            {
                "map": {"name": "Customs", "normalizedName": "customs"},
                "timestamp": "2026-09-01T05:27:51.000Z",
                "source": "external",
                "externalSource": "tarkov-goon-tracker.com",
            }
        ],
        "pve": [
            {
                "map": {"name": "Lighthouse", "normalizedName": "lighthouse"},
                "timestamp": "2026-09-01T06:17:18.000Z",
                "source": "external",
                "externalSource": "goon-tracker.com",
            },
            {
                "map": {"name": "Customs", "normalizedName": "customs"},
                "timestamp": "2026-08-31T18:25:28.671Z",
                "username": "tassenklon",
                "source": "killcounter",
            },
        ],
        "source": "merged",
    }
    bundle = goons.parse_stammtisch_bundle(payload)
    pve = goons.pick_latest_tracking(bundle["pve"])
    pvp = goons.pick_latest_tracking(bundle["pvp"])
    assert pve is not None
    assert pve["map"]["slug"] == "lighthouse"
    assert goons.project_status(pve, "pve")["map_name"] == "灯塔"
    assert pvp is not None
    assert goons.project_status(pvp, "pvp")["map_slug"] == "customs"


def test_pick_latest_skips_invalid_then_takes_newest() -> None:
    picked = goons.pick_latest_tracking(
        [
            {
                "id": "Invalid Date",
                "currentDate": "Invalid Date",
                "map": {"slug": "woods"},
            },
            {
                "id": "2026-09-01T04:00:00Z",
                "currentDate": "2026-09-01T04:00:00Z",
                "map": {"slug": "woods"},
            },
            {
                "id": "2026-09-01T06:00:00Z",
                "currentDate": "2026-09-01T06:00:00Z",
                "map": {"slug": "customs"},
            },
        ]
    )
    assert picked is not None
    assert picked["map"]["slug"] == "customs"


def test_refresh_all_publishes_on_change(monkeypatch) -> None:
    goons.reset_cache_for_tests()
    published: list[dict] = []
    monkeypatch.setattr(goons.hub, "publish", lambda payload: published.append(payload))
    monkeypatch.setattr(
        goons,
        "_fetch_bundle",
        lambda: {
            "pvp": [
                {
                    "id": "pvp-1",
                    "currentDate": "2026-09-01T06:00:00Z",
                    "map": {"slug": "customs"},
                }
            ],
            "pve": [
                {
                    "id": "pve-1",
                    "currentDate": "2026-09-01T06:10:00Z",
                    "map": {"slug": "lighthouse"},
                }
            ],
        },
    )
    changed = goons.refresh_all()
    assert changed == ["pvp", "pve"]
    assert len(published) == 1
    assert published[0]["event"] == "goons"
    assert published[0]["pve"]["map_slug"] == "lighthouse"
    assert published[0]["pvp"]["map_slug"] == "customs"
    assert goons.refresh_all() == []
    assert len(published) == 1


def test_get_status_fetches_when_empty(monkeypatch) -> None:
    goons.reset_cache_for_tests()
    monkeypatch.setattr(
        goons,
        "_fetch_bundle",
        lambda: {
            "pvp": [
                {
                    "id": "a",
                    "currentDate": "2026-09-01T01:00:00Z",
                    "map": {"slug": "woods"},
                }
            ],
            "pve": [],
        },
    )
    status = goons.get_status("pvp")
    assert status["map_name"] == "森林"


def test_refresh_keeps_previous_when_bundle_empty(monkeypatch) -> None:
    goons.reset_cache_for_tests()
    monkeypatch.setattr(goons.hub, "publish", lambda payload: None)
    monkeypatch.setattr(
        goons,
        "_fetch_bundle",
        lambda: {
            "pvp": [
                {
                    "id": "a",
                    "currentDate": "2026-09-01T01:00:00Z",
                    "map": {"slug": "woods"},
                }
            ],
            "pve": [
                {
                    "id": "b",
                    "currentDate": "2026-09-01T01:00:00Z",
                    "map": {"slug": "customs"},
                }
            ],
        },
    )
    goons.refresh_all()
    monkeypatch.setattr(goons, "_fetch_bundle", lambda: {"pvp": [], "pve": []})
    assert goons.refresh_all() == []
    assert goons.get_cached("pvp")["map_slug"] == "woods"


def test_status_fingerprint() -> None:
    a = goons.project_status(
        {
            "id": "1",
            "currentDate": "2026-09-01T06:00:00Z",
            "map": {"slug": "customs"},
        },
        "pve",
    )
    b = json.loads(json.dumps(a))
    assert goons.status_fingerprint(a) == goons.status_fingerprint(b)
    b["map_slug"] = "woods"
    assert goons.status_fingerprint(a) != goons.status_fingerprint(b)
