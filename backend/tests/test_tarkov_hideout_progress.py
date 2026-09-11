"""藏身处规划器：默认仓库 1、设施前置、降级级联。"""

from __future__ import annotations

import pytest

from app.services.tarkov.hideout_progress import (
    apply_level,
    can_set_level,
    default_level,
    filled_levels,
    skill_req_met,
    station_req_met,
    trader_req_met,
)


def _station(ident: str, slug: str, specs: list[dict]) -> dict:
    return {"id": ident, "slug": slug, "levels": specs}


def _catalog() -> list[dict]:
    return [
        _station(
            "stash",
            "stash",
            [
                {"level": 1, "station_requirements": []},
                {
                    "level": 2,
                    "station_requirements": [{"station_id": "gen", "level": 1}],
                },
            ],
        ),
        _station(
            "gen",
            "generator",
            [
                {"level": 1, "station_requirements": []},
                {
                    "level": 2,
                    "station_requirements": [{"station_id": "stash", "level": 2}],
                },
            ],
        ),
        _station(
            "bench",
            "workbench",
            [
                {
                    "level": 1,
                    "station_requirements": [{"station_id": "gen", "level": 1}],
                },
                {
                    "level": 2,
                    "station_requirements": [{"station_id": "gen", "level": 2}],
                },
            ],
        ),
    ]


def test_stash_defaults_to_one_others_zero() -> None:
    levels = filled_levels(_catalog(), {})
    assert levels["stash"] == 1
    assert levels["gen"] == 0
    assert levels["bench"] == 0
    assert default_level({"slug": "stash"}) == 1
    assert default_level({"slug": "workbench"}) == 0


def test_upgrade_blocked_until_station_prereq() -> None:
    stations = _catalog()
    levels = filled_levels(stations, {})
    by_id = {row["id"]: row for row in stations}
    assert can_set_level(by_id["bench"], 1, levels, by_id) is False
    with pytest.raises(ValueError, match="前置"):
        apply_level(stations, levels, "bench", 1)
    next_levels = apply_level(stations, levels, "gen", 1)
    assert next_levels["gen"] == 1
    assert apply_level(stations, next_levels, "bench", 1)["bench"] == 1


def test_downgrade_cascades_dependents() -> None:
    stations = _catalog()
    filled = filled_levels(stations, {"stash": 2, "gen": 2, "bench": 2})
    mid = apply_level(stations, filled, "gen", 1)
    assert mid["gen"] == 1
    assert mid["bench"] == 1
    assert mid["stash"] == 2
    out = apply_level(stations, mid, "gen", 0)
    assert out["gen"] == 0
    assert out["bench"] == 0
    assert out["stash"] == 1


def test_stash_cannot_drop_to_zero() -> None:
    stations = _catalog()
    levels = filled_levels(stations, {"stash": 1})
    assert apply_level(stations, levels, "stash", 0)["stash"] == 1
    assert apply_level(stations, {"stash": 2, "gen": 1, "bench": 0}, "stash", 1)[
        "stash"
    ] == 1


def test_skip_levels_rejected() -> None:
    stations = _catalog()
    with pytest.raises(ValueError, match="逐级"):
        apply_level(stations, {"gen": 0}, "gen", 2)


def test_future_trader_skill_unset_until_user_data() -> None:
    req_t = {"id": "prapor", "slug": "prapor", "level": 2}
    req_s = {"skill_id": "HideoutManagement", "skill": "藏身处管理", "level": 5}
    assert trader_req_met(req_t, None) is None
    assert skill_req_met(req_s, None) is None
    assert trader_req_met(req_t, {"prapor": 2}) is True
    assert trader_req_met(req_t, {"prapor": 1}) is False
    assert skill_req_met(req_s, {"HideoutManagement": 5}) is True
    assert station_req_met({"station_id": "gen", "level": 1}, {"gen": 1}, {}) is True
