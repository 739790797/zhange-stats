"""Public Minecraft overview helpers."""

from __future__ import annotations

from app.services.minecraft.mod_catalog import (
    mcmod_class_id,
    pick_curseforge_url,
    pick_modrinth_hit,
    pick_modrinth_mod_url,
    query_from_jar,
)
from app.services.minecraft.profile import (
    jar_display_name,
    merge_overview_mods,
    merge_roster,
    parse_whitelist_json,
)


def test_jar_display_name_strips_extension():
    assert jar_display_name("lithium-fabric-0.12.7.jar") == "lithium-fabric-0.12.7"
    assert jar_display_name("README") == "README"


def test_parse_whitelist_json():
    rows = parse_whitelist_json(
        '[{"uuid":"aaa","name":"Steve"},{"id":"bbb","name":"Alex"}]'
    )
    assert rows == [
        {"name": "Steve", "id": "aaa"},
        {"name": "Alex", "id": "bbb"},
    ]
    assert parse_whitelist_json("not-json") == []
    assert parse_whitelist_json("{}") == []


def test_merge_overview_mods_prefers_applied_titles():
    live = [
        {"filename": "lithium.jar", "project_title": "lithium", "version_number": ""},
        {"filename": "extra.jar", "project_title": "extra", "version_number": ""},
    ]
    applied = [
        {"filename": "lithium.jar", "project_title": "Lithium", "version_number": "0.12"},
    ]
    merged = merge_overview_mods(live, applied)
    assert merged[0]["project_title"] == "Lithium"
    assert merged[0]["version_number"] == "0.12"
    assert merged[1]["filename"] == "extra.jar"


def test_merge_overview_mods_falls_back_to_applied_when_unread():
    applied = [{"filename": "a.jar", "project_title": "A", "version_number": "1"}]
    assert merge_overview_mods(None, applied) == applied
    assert merge_overview_mods([], applied) == []


def test_query_from_jar_strips_loader_and_version():
    assert (
        query_from_jar("DistantHorizons-2.3.0-1.21.1-fabric-neoforge.jar")
        == "DistantHorizons"
    )
    assert query_from_jar("Jade-1.21.1-NeoForge-15.10.3.jar") == "Jade"
    assert query_from_jar("Chunky-NeoForge-1.4.23.jar") == "Chunky"


def test_pick_modrinth_hit_prefers_exact_slug():
    hit = pick_modrinth_hit(
        [
            {
                "project_type": "mod",
                "slug": "distanthorizonsapi",
                "title": "Distant Horizons API",
            },
            {
                "project_type": "mod",
                "slug": "distanthorizons",
                "title": "Distant Horizons",
            },
        ],
        "DistantHorizons",
    )
    assert hit is not None
    assert hit["slug"] == "distanthorizons"


def test_merge_roster_marks_online_from_sample():
    roster = merge_roster(
        [{"name": "BaiYi", "id": "aaa"}],
        [{"name": "BaiYi", "id": "aaa"}, {"name": "Steve", "id": "bbb"}],
        [],
    )
    assert roster[0]["name"] == "BaiYi"
    assert roster[0]["online"] is True
    assert roster[1]["name"] == "Steve"
    assert roster[1]["online"] is False


def test_pick_curseforge_prefers_mc_mods():
    links = [
        {"text": "CurseForge: Bukkit", "url": "https://www.curseforge.com/minecraft/bukkit-plugins/x"},
        {"text": "CurseForge", "url": "https://www.curseforge.com/minecraft/mc-mods/distant-horizons"},
    ]
    assert pick_curseforge_url(links).endswith("/mc-mods/distant-horizons")
    assert pick_modrinth_mod_url(
        [
            {"url": "https://modrinth.com/plugin/x"},
            {"url": "https://modrinth.com/mod/distanthorizons"},
        ]
    ).endswith("/mod/distanthorizons")


def test_mcmod_class_id_from_search_hit():
    assert (
        mcmod_class_id(
            {
                "address": "https://www.mcmod.cn/class/5009.html",
                "data": {"mcmod_id": "5009"},
            }
        )
        == "5009"
    )
    assert mcmod_class_id({"address": "https://www.mcmod.cn/class/12.html"}) == "12"
