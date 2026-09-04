"""Unit tests for tarkov trader parse / filter / pagination."""

from __future__ import annotations

from app.services.tarkov import traders as traders
from app.services.tarkov.ammo import SOURCE_JSON_API

PRAPOR = "54cb50c76803fa8b248b4571"
THERAPIST = "54cb57776803fa99248b456e"


def _envelope() -> dict:
    return {
        "traders": {
            PRAPOR: {
                "normalizedName": "prapor",
                "name": "Prapor",
                "description": f"{PRAPOR} Description",
                "resetTime": "2026-08-13T12:00:00.000Z",
                "imageLink": "https://assets.tarkov.dev/prapor.webp",
                "currency": {"name": "RUB"},
                "levels": [
                    {
                        "level": 1,
                        "requiredPlayerLevel": 1,
                        "requiredReputation": 0,
                        "requiredCommerce": 0,
                    },
                    {
                        "level": 2,
                        "requiredPlayerLevel": 15,
                        "requiredReputation": 0.2,
                        "requiredCommerce": 1_000_000,
                    },
                ],
            },
            THERAPIST: {
                "normalizedName": "therapist",
                "name": "Therapist",
                "levels": [{"level": 1, "requiredPlayerLevel": 1}],
            },
            "extra-id": {
                "normalizedName": "taran",
                "name": "Taran",
                "levels": [],
            },
        },
        "locale": {
            f"{PRAPOR} Description": "普拉普尔负责向 BEAR 提供武器与弹药。",
        },
        "offers": [
            {
                "trader_id": PRAPOR,
                "item_id": "i1",
                "name": "VKBO军用背包",
                "short_name": "VKBO",
                "icon_link": "",
                "types": ["backpack"],
                "avg24h_price": 60000,
                "last_low_price": 55000,
                "price": 49222,
                "price_rub": 49222,
                "currency": "RUB",
                "min_trader_level": 1,
                "buy_limit": None,
                "task_unlock_id": "",
                "task_unlock_name": "",
            },
            {
                "trader_id": PRAPOR,
                "item_id": "i2",
                "name": "AK-74N",
                "short_name": "AK-74N",
                "icon_link": "",
                "types": ["gun"],
                "avg24h_price": 80000,
                "last_low_price": 70000,
                "price": 100,
                "price_rub": 100,
                "currency": "RUB",
                "min_trader_level": 2,
                "buy_limit": 1,
                "task_unlock_id": "t1",
                "task_unlock_name": "Debut",
            },
            {
                "trader_id": THERAPIST,
                "item_id": "i3",
                "name": "AI-2",
                "short_name": "AI-2",
                "icon_link": "",
                "types": ["meds"],
                "avg24h_price": 2000,
                "last_low_price": 1500,
                "price": 12,
                "price_rub": 1400,
                "currency": "EUR",
                "min_trader_level": 1,
                "buy_limit": None,
                "task_unlock_id": "",
                "task_unlock_name": "",
            },
        ],
    }


def test_parse_locale_and_english_names():
    rows = traders.parse_trader_rows(_envelope())
    by_slug = {r["slug"]: r for r in rows}
    assert [r["slug"] for r in rows[:3]] == ["prapor", "therapist", "taran"]
    assert by_slug["prapor"]["english"] == "Prapor"
    assert by_slug["prapor"]["chinese"] == ""
    assert by_slug["prapor"]["name"] == "Prapor"
    assert by_slug["prapor"]["search_alias"] == "俄商 售货员"
    assert by_slug["prapor"]["description"].startswith("普拉普尔")
    assert by_slug["prapor"]["offer_count"] == 2
    assert by_slug["prapor"]["wiki_link"].endswith("/Prapor")
    assert by_slug["therapist"]["chinese"] == ""
    assert by_slug["therapist"]["name"] == "Therapist"
    assert by_slug["taran"]["english"] == "Taran"
    assert by_slug["taran"]["chinese"] == ""
    assert by_slug["taran"]["offer_count"] == 0


def test_filter_level_and_search():
    offers = traders._offers_list(_envelope())
    lv1 = traders.filter_offers(offers, trader_id=PRAPOR, level=1)
    assert [r["item_id"] for r in lv1] == ["i1"]
    hit = traders.filter_offers(offers, trader_id=PRAPOR, q="vkbo")
    assert [r["item_id"] for r in hit] == ["i1"]
    therapist = traders.filter_offers(offers, trader_id=THERAPIST)
    assert [r["item_id"] for r in therapist] == ["i3"]


def test_paginate_clamps_page():
    rows = [{"id": str(i)} for i in range(5)]
    paged = traders.paginate_offers(rows, page=9, page_size=2)
    assert paged["offer_count"] == 5
    assert paged["page"] == 3
    assert paged["page_size"] == 2
    assert [r["id"] for r in paged["items"]] == ["4"]

    empty = traders.paginate_offers([], page=3, page_size=50)
    assert empty["items"] == []
    assert empty["page"] == 1


def test_extract_offers_from_items():
    payload = {
        "items": {
            "i1": {
                "id": "i1",
                "name": "VKBO",
                "shortName": "VKBO",
                "types": ["backpack"],
                "avg24hPrice": 60000,
                "lastLowPrice": 55000,
                "baseImageLink": "https://img/i1.webp",
                "buyFromTrader": [
                    {
                        "trader": PRAPOR,
                        "price": 49222,
                        "priceRUB": 49222,
                        "currency": "RUB",
                        "minTraderLevel": 1,
                        "buyLimit": None,
                        "taskUnlock": None,
                    }
                ],
            },
            "i2": {
                "id": "i2",
                "name": "no offers",
                "buyFromTrader": [],
            },
        },
        "locale": {"i1 Name": "VKBO军用背包"},
    }
    offers = traders.extract_offers_from_items(SOURCE_JSON_API, payload)
    assert len(offers) == 1
    row = offers[0]
    assert row["trader_id"] == PRAPOR
    assert row["item_id"] == "i1"
    assert row["name"] == "VKBO军用背包"
    assert row["price"] == 49222
    assert row["min_trader_level"] == 1
    assert row["avg24h_price"] == 60000
