"""Minecraft entity list parse / classify."""

from __future__ import annotations

from app.services.minecraft.entities import (
    entity_category,
    parse_entity_list,
    summarize_entities,
)


def test_parse_neoforge_multiline_entity_list():
    raw = (
        "Total: 8\n"
        " 5: minecraft:item\n"
        " 2: minecraft:zombie\n"
        " 1: create:carriage\n"
    )
    rows = parse_entity_list(raw)
    assert rows == [
        {"id": "minecraft:item", "count": 5},
        {"id": "minecraft:zombie", "count": 2},
        {"id": "create:carriage", "count": 1},
    ]


def test_parse_forge_inline_entity_list():
    raw = (
        "Total: 24  12: minecraft:chicken  5: minecraft:cow  "
        "2: minecraft:item  2: minecraft:item_frame"
    )
    rows = {row["id"]: row["count"] for row in parse_entity_list(raw)}
    assert rows["minecraft:chicken"] == 12
    assert rows["minecraft:item_frame"] == 2


def test_classify_and_summarize_categories():
    summary = summarize_entities(
        {
            "minecraft:player": 2,
            "minecraft:item": 40,
            "minecraft:zombie": 10,
            "minecraft:cow": 4,
            "minecraft:arrow": 3,
            "minecraft:oak_boat": 1,
            "minecraft:armor_stand": 2,
            "create:carriage": 7,
        },
        command="neoforge entity list",
        worlds=[{"id": "minecraft:overworld", "total": 69}],
    )
    by_key = {row["key"]: row["count"] for row in summary["categories"]}
    assert summary["total"] == 69
    assert by_key["player"] == 2
    assert by_key["drop"] == 40
    assert by_key["hostile"] == 10
    assert by_key["passive"] == 4
    assert by_key["projectile"] == 3
    assert by_key["vehicle"] == 1
    assert by_key["display"] == 2
    assert by_key["mod"] == 7
    assert entity_category("minecraft:hopper_minecart") == "vehicle"
    assert summary["types"][0]["id"] == "minecraft:item"
