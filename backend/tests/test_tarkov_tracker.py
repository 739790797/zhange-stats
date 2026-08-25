"""Unit tests for Tarkov Tracker token parse / progress projection."""

from __future__ import annotations

import pytest

from app.services.tarkov import tracker as tracker


def test_parse_token_accepts_org_format():
    token, mode = tracker.parse_token("PVP_deadbeefcafefeed01")
    assert token == "PVP_deadbeefcafefeed01"
    assert mode == "pvp"
    _, pve = tracker.parse_token("PVE_aaaaaaaaaaaaaaaaaa")
    assert pve == "pve"
    _, seasonal = tracker.parse_token("SZN_ababababababababab")
    assert seasonal == "seasonal"


def test_parse_token_rejects_legacy_and_short():
    with pytest.raises(tracker.TarkovTrackerError):
        tracker.parse_token("tt_legacy")
    with pytest.raises(tracker.TarkovTrackerError):
        tracker.parse_token("PVP_nothex!!!!!!!!!!!!!!")
    with pytest.raises(tracker.TarkovTrackerError):
        tracker.parse_token("")


def test_parse_progress_counts_and_level():
    payload = {
        "success": True,
        "data": {
            "displayName": "Pigeon",
            "userId": "u1",
            "playerLevel": 42,
            "gameEdition": 4,
            "pmcFaction": "BEAR",
            "tasksProgress": [
                {"id": "a", "complete": True, "failed": False},
                {"id": "b", "complete": False, "failed": True},
                {"id": "c", "complete": False, "failed": False},
            ],
            "taskObjectivesProgress": [],
            "hideoutModulesProgress": [],
            "hideoutPartsProgress": [],
        },
        "meta": {"self": "u1", "gameMode": "pvp"},
    }
    out = tracker.parse_progress(payload)
    assert out["display_name"] == "Pigeon"
    assert out["player_level"] == 42
    assert out["pmc_faction"] == "BEAR"
    assert out["tasks_complete"] == 1
    assert out["tasks_failed"] == 1
    blob = tracker.dump_progress_json(out)
    loaded = tracker.load_progress_snapshot(
        type("Row", (), {"progress_json": blob, "player_level": 1, "pmc_faction": "", "game_mode": ""})()
    )
    assert loaded is not None
    assert loaded["tasks"]["a"]["complete"] is True
    assert loaded["player_level"] == 42


def test_game_mode_label():
    assert tracker.game_mode_label("pve") == "PVE"
    assert tracker.game_mode_label("seasonal") == "赛季"
    assert tracker.game_mode_label("pvp") == "PVP"
