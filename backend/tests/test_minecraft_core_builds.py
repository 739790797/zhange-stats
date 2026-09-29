from app.services.minecraft.core_builds import (
    arclight_jar_name,
    builds_from_listing,
)


def test_arclight_listing_skips_latest_links_and_names_the_jar():
    files = [
        {"name": "latest-stable", "type": "link", "link": "https://example/latest"},
        {"name": "1.0.1-8ec9529", "type": "object", "link": "https://example/1.0.1"},
        {"name": "../evil", "type": "object", "link": "https://example/evil"},
    ]
    rows = builds_from_listing(files, limit=10)
    assert [row["name"] for row in rows] == ["1.0.1-8ec9529"]
    assert arclight_jar_name("neoforge", "1.21.1", rows[0]["name"]) == (
        "arclight-neoforge-1.21.1-1.0.1-8ec9529.jar"
    )
