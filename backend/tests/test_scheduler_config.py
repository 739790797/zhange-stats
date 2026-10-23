from __future__ import annotations

from app.services import scheduler_config
from app.services.upstream_repos import (
    DEFAULT_REPO_SYNC_TIMEOUT_MINUTES,
    MAX_REPO_SYNC_TIMEOUT_MINUTES,
    REPO_SYNC_JOB_IDS,
)


def test_git_repo_sync_timeouts_default_to_thirty_minutes_and_are_independent(
    monkeypatch,
) -> None:
    monkeypatch.setattr(scheduler_config, "read_json", lambda _name: None)

    config = scheduler_config.load_scheduler_config()

    assert DEFAULT_REPO_SYNC_TIMEOUT_MINUTES == 30
    assert {
        config[job_id]["timeout_minutes"] for job_id in REPO_SYNC_JOB_IDS.values()
    } == {30}


def test_git_repo_sync_timeout_can_be_configured_per_job(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler_config,
        "read_json",
        lambda _name: {
            "scheduler": {
                "arknights_repo_sync": {"timeout_minutes": 95},
                "endfield_repo_sync": {"timeout_minutes": 40},
            }
        },
    )

    config = scheduler_config.load_scheduler_config()

    assert config["arknights_repo_sync"]["timeout_minutes"] == 95
    assert config["endfield_repo_sync"]["timeout_minutes"] == 40
    assert config["tarkov_overlay_repo_sync"]["timeout_minutes"] == 30
    assert config["tarkov_svg_repo_sync"]["timeout_minutes"] == 30


def test_git_repo_sync_timeout_is_bounded(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler_config,
        "read_json",
        lambda _name: {
            "scheduler": {
                "endfield_repo_sync": {"timeout_minutes": 0},
                "arknights_repo_sync": {"timeout_minutes": MAX_REPO_SYNC_TIMEOUT_MINUTES + 1},
            }
        },
    )

    config = scheduler_config.load_scheduler_config()

    assert config["endfield_repo_sync"]["timeout_minutes"] == 1
    assert config["arknights_repo_sync"]["timeout_minutes"] == MAX_REPO_SYNC_TIMEOUT_MINUTES


def test_git_repo_sync_timeout_is_saved_independently(monkeypatch) -> None:
    written: dict[str, object] = {}
    monkeypatch.setattr(scheduler_config, "read_json", lambda _name: None)
    monkeypatch.setattr(
        scheduler_config,
        "write_json",
        lambda _name, value: written.update(value),
    )

    saved = scheduler_config.save_scheduler_config(
        None,
        {
            "jobs": {
                "arknights_repo_sync": {"timeout_minutes": 100},
                "endfield_repo_sync": {"timeout_minutes": 45},
            }
        },
        commit=False,
    )

    stored = written["scheduler"]
    assert isinstance(stored, dict)
    assert saved["arknights_repo_sync"]["timeout_minutes"] == 100
    assert saved["endfield_repo_sync"]["timeout_minutes"] == 45
    assert saved["tarkov_svg_repo_sync"]["timeout_minutes"] == 30
    assert stored["arknights_repo_sync"]["timeout_minutes"] == 100
