"""地图筛选喜好与网页默认值对齐，并按账号整份保存。"""

from app.services.tarkov.map_filters import normalize_map_filters


def test_missing_fields_match_web_defaults() -> None:
    prefs = normalize_map_filters({})
    assert prefs["style"] == "svg"
    assert prefs["filterPanelOpen"] is True
    assert prefs["showLabels"] is True
    assert prefs["showQuests"] is True
    assert prefs["showLootContainers"] is False
    assert prefs["showLootLoose"] is False
    assert prefs["extractKinds"] == {"pmc": True, "scav": True, "shared": True, "transit": True}
    assert prefs["spawnKinds"]["boss"] is True
    assert prefs["floorsByMap"] == {}
    assert prefs["hazardKinds"] == {}


def test_keeps_per_map_floor_and_tile_style() -> None:
    prefs = normalize_map_filters(
        {
            "style": "tile",
            "floorsByMap": {"customs": "1st Floor", "factory": "", "bad": 3},
            "showLootContainers": True,
            "lootContainerKinds": {"wooden-crate": True, "": False, "x" * 80: True},
        }
    )
    assert prefs["style"] == "tile"
    assert prefs["floorsByMap"] == {"customs": "1st Floor", "factory": ""}
    assert prefs["showLootContainers"] is True
    assert prefs["lootContainerKinds"] == {"wooden-crate": True}


def test_collapsed_groups_keep_only_known_closed_ones() -> None:
    prefs = normalize_map_filters(
        {"filterGroupsCollapsed": {"lootable": True, "extracts": False, "nope": True}}
    )
    assert prefs["filterGroupsCollapsed"] == {"lootable": True}


def test_caps_kind_maps() -> None:
    kinds = {f"kind-{index}": True for index in range(100)}
    prefs = normalize_map_filters({"hazardKinds": kinds})
    assert len(prefs["hazardKinds"]) == 80
