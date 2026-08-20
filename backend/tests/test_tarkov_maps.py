"""Unit tests for tarkov map projection / aliases."""

from __future__ import annotations

from app.services.tarkov_maps import (
    HUB_SKIP,
    parse_map_rows,
    resolve_map_slug,
)


def _payload() -> dict:
    return {
        "maps": {
            "factory": {
                "id": "factory",
                "name": "Factory",
                "normalizedName": "factory",
                "raidDuration": 20,
                "players": "4-6",
                "wiki": "https://wiki/factory",
                "extracts": [
                    {"id": "e1", "name": "Gate 3", "faction": "pmc"},
                    {"id": "e2", "name": "Cellars", "faction": "scav"},
                ],
                "bosses": [{"mob": "bossTagilla", "spawnChance": 0.3}],
            },
            "night-factory": {
                "id": "night-factory",
                "name": "Factory",
                "normalizedName": "night-factory",
                "raidDuration": 25,
                "players": "4-5",
                "parent": "factory",
            },
            "the-lab": {
                "id": "thelab",
                "name": "The Lab",
                "normalizedName": "the-lab",
                "raidDuration": 40,
                "players": "6-10",
            },
            "streets-of-tarkov": {
                "id": "streets",
                "name": "Streets of Tarkov",
                "normalizedName": "streets-of-tarkov",
                "raidDuration": 50,
                "players": "9-16",
            },
            "openworld": {
                "id": "openworld",
                "name": "Openworld",
                "normalizedName": "openworld",
            },
        },
        "mobs": {
            "bossTagilla": {
                "id": "bossTagilla",
                "name": "Tagilla",
                "normalizedName": "tagilla",
            }
        },
        "locale": {
            "thelab Name": "实验室",
            "Gate 3": "3 号门",
        },
    }


def test_resolve_map_slug_aliases() -> None:
    assert resolve_map_slug("lab") == "the-lab"
    assert resolve_map_slug("streets") == "streets-of-tarkov"
    assert resolve_map_slug("labyrinth") == "the-labyrinth"
    assert resolve_map_slug("factory-night") == "night-factory"
    assert resolve_map_slug("customs") == "customs"


def test_parse_map_rows_variants_and_extracts() -> None:
    rows = parse_map_rows(_payload())
    by_slug = {str(r["slug"]): r for r in rows}
    assert "factory" in by_slug
    assert by_slug["night-factory"]["parent_slug"] == "factory"
    assert by_slug["openworld"]["slug"] in HUB_SKIP
    factory = by_slug["factory"]
    assert factory["raid_duration"] == 20
    assert factory["players"] == "4-6"
    assert factory["thumb_link"].endswith("/maps/factory_thumb.jpg")
    assert factory["interactive_url"].endswith("/map/factory")
    names = {row["name"] for row in factory["extracts"]}
    assert "3 号门" in names
    bosses = factory["bosses"]
    assert bosses and bosses[0]["slug"] == "tagilla"
    assert bosses[0]["spawn_chance"] == 30
