"""Unit tests for generic tarkov item catalog parse/filter."""

from __future__ import annotations

from app.services import tarkov_catalog as catalog
from app.services.tarkov_ammo import SOURCE_GRAPHQL, SOURCE_JSON_API
from app.services.tarkov_items import GRAPHQL_SPLIT_FORMAT, TarkovItemsError


HEADSET_CAT = "5b5f6f3c86f774094242ef87"
ARMOR_CAT = "5b5f701386f774093f2ecf0f"


def _json_envelope() -> dict:
    return {
        "items": {
            "data": {
                "items": {
                    "hs1": {
                        "id": "hs1",
                        "name": "hs1 Name",
                        "shortName": "GSHSS",
                        "types": ["headphones"],
                        "weight": 0.5,
                        "width": 2,
                        "height": 2,
                        "basePrice": 12000,
                        "avg24hPrice": 18000,
                        "lastLowPrice": 16500,
                        "baseImageLink": "https://example/hs.webp",
                        "handbookCategories": {HEADSET_CAT: {"id": HEADSET_CAT}},
                        "properties": {
                            "propertiesType": "ItemPropertiesHeadphones",
                            "distanceModifier": 1.2,
                            "slots": [{"huge": True}],
                        },
                    },
                    "ar1": {
                        "id": "ar1",
                        "name": "ar1 Name",
                        "shortName": "6B13",
                        "types": ["armor"],
                        "handbookCategories": [
                            {"id": ARMOR_CAT},
                        ],
                        "properties": {"propertiesType": "ItemPropertiesArmor"},
                    },
                    "grip1": {
                        "id": "grip1",
                        "name": "grip1 Name",
                        "shortName": "AK grip",
                        "types": ["pistolGrip"],
                        "handbookCategories": {},
                        "properties": {"propertiesType": "ItemPropertiesWeaponMod"},
                    },
                }
            }
        },
        "locale": {
            "hs1 Name": "GSSh-01",
            "ar1 Name": "6B13 装甲",
            "grip1 Name": "AK 握把",
        },
    }


def test_parse_and_filter_by_handbook_category():
    rows = catalog.parse_catalog_items(SOURCE_JSON_API, _json_envelope())
    assert {r["id"] for r in rows} == {"hs1", "ar1", "grip1"}
    headset = catalog.filter_catalog_items(rows, category_ids=[HEADSET_CAT])[0]
    assert headset["id"] == "hs1"
    assert headset["avg24h_price"] == 18000
    assert headset["last_low_price"] == 16500
    assert headset["properties"]["distanceModifier"] == 1.2
    assert "slots" not in headset["properties"]
    assert catalog.filter_catalog_items(rows, category_ids=[ARMOR_CAT])[0]["name"] == "6B13 装甲"


def test_filter_by_type():
    rows = catalog.parse_catalog_items(SOURCE_JSON_API, _json_envelope())
    grips = catalog.filter_catalog_items(rows, types=["pistolGrip"])
    assert [r["id"] for r in grips] == ["grip1"]


def test_filter_type_aliases_silencer_and_headset():
    rows = [
        {"id": "sup1", "types": ["suppressor"], "handbook_ids": []},
        {"id": "hp1", "types": ["headphones"], "handbook_ids": []},
    ]
    assert [r["id"] for r in catalog.filter_catalog_items(rows, types=["silencer"])] == [
        "sup1"
    ]
    assert [r["id"] for r in catalog.filter_catalog_items(rows, types=["headset"])] == [
        "hp1"
    ]


def test_extract_detail_uses_locale():
    detail = catalog.extract_item_detail(SOURCE_JSON_API, _json_envelope(), "hs1")
    assert detail is not None
    assert detail["name"] == "GSSh-01"
    assert detail["item"]["shortName"] == "GSHSS"
    assert detail["properties"]["propertiesType"] == "ItemPropertiesHeadphones"


def test_payload_has_full_items():
    assert catalog.payload_has_full_items(SOURCE_JSON_API, _json_envelope()) is True
    split = {"format": GRAPHQL_SPLIT_FORMAT, "ammo": {}, "guns": {}}
    assert catalog.payload_has_full_items(SOURCE_GRAPHQL, split) is False


def test_list_catalog_requires_filter():
    try:
        catalog.filter_catalog_items([], category_ids=[], types=[])
    except TarkovItemsError:
        raise AssertionError("pure filter with empty should return all empty")
    assert catalog.filter_catalog_items([], category_ids=[], types=[]) == []


def test_search_catalog_items_matches_name_short_id():
    rows = catalog.parse_catalog_items(SOURCE_JSON_API, _json_envelope())
    assert [r["id"] for r in catalog.search_catalog_items(rows, "6B13")] == ["ar1"]
    assert [r["id"] for r in catalog.search_catalog_items(rows, "gsh")] == ["hs1"]
    assert [r["id"] for r in catalog.search_catalog_items(rows, "grip1")] == ["grip1"]
    assert catalog.search_catalog_items(rows, "  ") == rows


def test_compact_properties_keeps_grids_drops_slots():
    compact = catalog._compact_properties(
        {
            "capacity": 20,
            "grids": [{"width": 4, "height": 5, "cells": [1, 2]}],
            "slots": [{"id": "x"}],
            "material": {"id": "m1", "name": "Aramid"},
        }
    )
    assert compact["capacity"] == 20
    assert compact["grids"] == [{"width": 4, "height": 5}]
    assert "slots" not in compact
    assert compact["material"] == {"id": "m1", "name": "Aramid"}


def test_paginate_catalog_items_clamps_page():
    rows = [{"id": str(i)} for i in range(5)]
    paged = catalog.paginate_catalog_items(rows, page=9, page_size=2)
    assert paged["item_count"] == 5
    assert paged["page"] == 3
    assert paged["page_size"] == 2
    assert [r["id"] for r in paged["items"]] == ["4"]

    empty = catalog.paginate_catalog_items([], page=3, page_size=50)
    assert empty["items"] == []
    assert empty["item_count"] == 0
    assert empty["page"] == 1
    assert empty["page_size"] == 50

    capped = catalog.paginate_catalog_items(rows, page=1, page_size=1000)
    assert capped["page_size"] == catalog.CATALOG_PAGE_SIZE_MAX
    assert len(capped["items"]) == 5
