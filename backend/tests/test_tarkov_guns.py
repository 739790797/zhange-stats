"""Unit tests for tarkov gun parsers."""

from __future__ import annotations

import json

import pytest

from app.services import tarkov_guns as svc
from app.services.tarkov_ammo import SOURCE_GRAPHQL, SOURCE_JSON_API


def test_parse_graphql_guns():
    payload = {
        "data": {
            "items": [
                {
                    "id": "5644bd2b4bdc2d3b4c8b4572",
                    "name": "AK-74N",
                    "shortName": "AK-74N",
                    "iconLink": "https://example/icon.webp",
                    "types": ["gun"],
                    "categories": [
                        {"id": "5447b5f14bdc2d61278b4567", "normalizedName": "assault-rifle"}
                    ],
                    "properties": {
                        "__typename": "ItemPropertiesWeapon",
                        "caliber": "Caliber545x39",
                        "fireRate": 650,
                        "ergonomics": 31,
                        "recoilVertical": 96,
                        "recoilHorizontal": 244,
                        "effectiveDistance": 650,
                        "fireModes": ["single", "fullauto"],
                        "defaultAmmo": {"id": "ammo1"},
                        "allowedAmmo": [{"id": "ammo1"}, {"id": "ammo2"}],
                    },
                },
                {
                    "id": "preset1",
                    "types": ["gun", "preset"],
                    "properties": {"__typename": "ItemPropertiesWeapon", "caliber": "Caliber545x39"},
                },
                {
                    "id": "rsp30",
                    "name": "RSP-30",
                    "shortName": "RSP-30",
                    "wikiLink": "https://escapefromtarkov.fandom.com/wiki/RSP-30_reactive_signal_cartridge_(Red)",
                    "types": ["gun", "specialSlot"],
                    "categories": [
                        {
                            "id": "5447bedf4bdc2d87278b4568",
                            "normalizedName": "grenade-launcher",
                        }
                    ],
                    "properties": {
                        "__typename": "ItemPropertiesWeapon",
                        "caliber": "Caliber26x75",
                        "fireRate": 30,
                        "slots": [],
                    },
                },
                {
                    "id": "fn40",
                    "name": "FN40GL",
                    "shortName": "FN40GL",
                    "types": ["gun", "wearable"],
                    "categories": [
                        {
                            "id": "5447bedf4bdc2d87278b4568",
                            "normalizedName": "grenade-launcher",
                        }
                    ],
                    "properties": {
                        "__typename": "ItemPropertiesWeapon",
                        "caliber": "Caliber40x46",
                        "fireRate": 30,
                        "ergonomics": 10,
                        "recoilVertical": 200,
                        "recoilHorizontal": 200,
                        "effectiveDistance": 100,
                        "fireModes": ["single"],
                    },
                },
            ]
        }
    }
    rows = svc.parse_graphql_guns(payload)
    assert len(rows) == 2
    assert rows[0]["item_id"] == "5644bd2b4bdc2d3b4c8b4572"
    assert rows[0]["caliber"] == "5.45x39mm"
    assert rows[0]["weapon_class"] == "assault-rifle"
    assert rows[0]["allowed_ammo_ids"] == ["ammo1", "ammo2"]
    assert rows[0]["fire_rate"] == 650
    assert rows[1]["item_id"] == "fn40"
    assert rows[1]["weapon_class"] == "grenade-launcher"
    assert rows[1]["caliber"] == "40x46mm"


def test_parse_graphql_guns_uses_default_preset():
    payload = {
        "data": {
            "items": [
                {
                    "id": "ak74n",
                    "name": "AK-74N",
                    "shortName": "AK-74N",
                    "iconLink": "https://example/receiver.webp",
                    "types": ["gun"],
                    "categories": [
                        {
                            "id": "5447b5f14bdc2d61278b4567",
                            "normalizedName": "assault-rifle",
                        }
                    ],
                    "properties": {
                        "__typename": "ItemPropertiesWeapon",
                        "caliber": "Caliber545x39",
                        "fireRate": 650,
                        "ergonomics": 31,
                        "recoilVertical": 96,
                        "recoilHorizontal": 244,
                        "effectiveDistance": 650,
                        "fireModes": ["single", "fullauto"],
                        "defaultAmmo": {"id": "ammo1"},
                        "allowedAmmo": [{"id": "ammo1"}],
                        "defaultPreset": {
                            "id": "ak74n-default",
                            "name": "AK-74N 默认",
                            "shortName": "AK-74N 默认",
                            "baseImageLink": "https://example/default.webp",
                            "types": ["preset"],
                            "properties": {
                                "__typename": "ItemPropertiesPreset",
                                "ergonomics": 48,
                                "recoilVertical": 80,
                                "recoilHorizontal": 210,
                            },
                        },
                    },
                },
                {
                    "id": "other-preset",
                    "name": "AK-74N Zenit",
                    "types": ["gun", "preset"],
                    "properties": {
                        "__typename": "ItemPropertiesPreset",
                        "ergonomics": 99,
                    },
                },
                {
                    "id": "fn40",
                    "name": "FN40GL",
                    "shortName": "FN40GL",
                    "types": ["gun", "wearable"],
                    "categories": [
                        {
                            "id": "5447bedf4bdc2d87278b4568",
                            "normalizedName": "grenade-launcher",
                        }
                    ],
                    "properties": {
                        "__typename": "ItemPropertiesWeapon",
                        "caliber": "Caliber40x46",
                        "fireRate": 30,
                        "ergonomics": 10,
                        "recoilVertical": 200,
                        "recoilHorizontal": 200,
                        "effectiveDistance": 100,
                        "fireModes": ["single"],
                    },
                },
            ]
        }
    }
    rows = {r["item_id"]: r for r in svc.parse_graphql_guns(payload)}
    assert set(rows) == {"ak74n-default", "fn40"}
    default = rows["ak74n-default"]
    assert default["name"] == "AK-74N 默认"
    assert default["icon_link"] == "https://example/default.webp"
    assert default["caliber"] == "5.45x39mm"
    assert default["fire_rate"] == 650
    assert default["ergonomics"] == 48
    assert default["recoil_vertical"] == 80
    assert default["recoil_horizontal"] == 210
    assert default["weapon_class"] == "assault-rifle"
    assert default["allowed_ammo_ids"] == ["ammo1"]


def test_parse_graphql_guns_missing_preset_falls_back_to_receiver():
    payload = {
        "data": {
            "items": [
                {
                    "id": "ak74n",
                    "name": "AK-74N",
                    "shortName": "AK-74N",
                    "types": ["gun"],
                    "categories": [
                        {
                            "id": "5447b5f14bdc2d61278b4567",
                            "normalizedName": "assault-rifle",
                        }
                    ],
                    "properties": {
                        "__typename": "ItemPropertiesWeapon",
                        "caliber": "Caliber545x39",
                        "fireRate": 650,
                        "ergonomics": 31,
                        "recoilVertical": 96,
                        "recoilHorizontal": 244,
                        "effectiveDistance": 650,
                        "fireModes": ["single"],
                        "defaultPreset": "missing-preset",
                    },
                }
            ]
        }
    }
    rows = svc.parse_graphql_guns(payload)
    assert len(rows) == 1
    assert rows[0]["item_id"] == "ak74n"
    assert rows[0]["ergonomics"] == 31


def test_parse_json_api_guns():
    payload = {
        "data": {
            "items": {
                "g1": {
                    "id": "g1",
                    "name": "g1 Name",
                    "shortName": "g1 ShortName",
                    "types": ["gun"],
                    "categories": ["5447b5e04bdc2d62278b4567"],
                    "iconLink": "https://example/g1.webp",
                    "properties": {
                        "propertiesType": "ItemPropertiesWeapon",
                        "caliber": "Caliber9x19PARA",
                        "fireRate": 900,
                        "ergonomics": 40,
                        "recoilVertical": 50,
                        "recoilHorizontal": 200,
                        "effectiveDistance": 200,
                        "fireModes": ["fullauto"],
                        "defaultAmmo": "a1",
                        "allowedAmmo": ["a1", "a2"],
                    },
                },
                "notgun": {
                    "id": "notgun",
                    "types": ["ammo"],
                    "properties": {"propertiesType": "ItemPropertiesAmmo"},
                },
            },
            "itemCategories": {
                "5447b5e04bdc2d62278b4567": {"normalizedName": "smg"},
            },
        }
    }
    locale = {"g1 Name": "MP5", "g1 ShortName": "MP5"}
    rows = svc.parse_json_api_guns(payload, locale=locale)
    assert len(rows) == 1
    assert rows[0]["short_name"] == "MP5"
    assert rows[0]["caliber"] == "9x19mm"
    assert rows[0]["weapon_class"] == "smg"


def test_parse_json_api_guns_uses_default_preset():
    payload = {
        "data": {
            "items": {
                "g1": {
                    "id": "g1",
                    "name": "g1 Name",
                    "shortName": "g1 ShortName",
                    "types": ["gun"],
                    "categories": ["5447b5e04bdc2d62278b4567"],
                    "iconLink": "https://example/g1.webp",
                    "properties": {
                        "propertiesType": "ItemPropertiesWeapon",
                        "caliber": "Caliber9x19PARA",
                        "fireRate": 900,
                        "ergonomics": 40,
                        "recoilVertical": 50,
                        "recoilHorizontal": 200,
                        "effectiveDistance": 200,
                        "fireModes": ["fullauto"],
                        "defaultAmmo": "a1",
                        "allowedAmmo": ["a1", "a2"],
                        "defaultPreset": "g1-default",
                    },
                },
                "g1-default": {
                    "id": "g1-default",
                    "name": "g1-default Name",
                    "shortName": "g1-default ShortName",
                    "types": ["preset"],
                    "baseImageLink": "https://example/g1-default.webp",
                    "properties": {
                        "propertiesType": "ItemPropertiesPreset",
                        "baseItem": "g1",
                        "ergonomics": 55.5,
                        "recoilVertical": 42,
                        "recoilHorizontal": 180,
                    },
                },
                "g1-zenit": {
                    "id": "g1-zenit",
                    "types": ["preset"],
                    "properties": {
                        "propertiesType": "ItemPropertiesPreset",
                        "baseItem": "g1",
                        "ergonomics": 80,
                    },
                },
            },
            "itemCategories": {
                "5447b5e04bdc2d62278b4567": {"normalizedName": "smg"},
            },
        }
    }
    locale = {
        "g1 Name": "MP5",
        "g1 ShortName": "MP5",
        "g1-default Name": "MP5 默认",
        "g1-default ShortName": "MP5 Default",
    }
    rows = svc.parse_json_api_guns(payload, locale=locale)
    assert len(rows) == 1
    assert rows[0]["item_id"] == "g1-default"
    assert rows[0]["name"] == "MP5 默认"
    assert rows[0]["short_name"] == "MP5 Default"
    assert rows[0]["icon_link"] == "https://example/g1-default.webp"
    assert rows[0]["caliber"] == "9x19mm"
    assert rows[0]["fire_rate"] == 900
    assert rows[0]["ergonomics"] == 55.5
    assert rows[0]["recoil_vertical"] == 42
    assert rows[0]["weapon_class"] == "smg"


def test_parse_json_api_guns_missing_preset_falls_back_to_receiver():
    payload = {
        "data": {
            "items": {
                "g1": {
                    "id": "g1",
                    "name": "g1 Name",
                    "types": ["gun"],
                    "categories": ["5447b5e04bdc2d62278b4567"],
                    "properties": {
                        "propertiesType": "ItemPropertiesWeapon",
                        "caliber": "Caliber9x19PARA",
                        "fireRate": 900,
                        "ergonomics": 40,
                        "recoilVertical": 50,
                        "recoilHorizontal": 200,
                        "effectiveDistance": 200,
                        "fireModes": ["fullauto"],
                        "defaultPreset": "missing",
                    },
                }
            },
            "itemCategories": {
                "5447b5e04bdc2d62278b4567": {"normalizedName": "smg"},
            },
        }
    }
    rows = svc.parse_json_api_guns(payload, locale={"g1 Name": "MP5"})
    assert len(rows) == 1
    assert rows[0]["item_id"] == "g1"
    assert rows[0]["name"] == "MP5"


def test_parse_gun_raw_json_envelope():
    envelope = {
        "items": {
            "data": {
                "items": {
                    "g1": {
                        "id": "g1",
                        "name": "g1 Name",
                        "shortName": "G",
                        "types": ["gun"],
                        "categories": ["5447b5cf4bdc2d65278b4567"],
                        "properties": {
                            "propertiesType": "ItemPropertiesWeapon",
                            "caliber": "Caliber9x18PM",
                            "fireRate": 30,
                            "ergonomics": 70,
                            "recoilVertical": 400,
                            "recoilHorizontal": 300,
                            "effectiveDistance": 50,
                            "fireModes": ["single"],
                            "defaultAmmo": "x",
                            "allowedAmmo": ["x"],
                        },
                    }
                }
            }
        },
        "locale": {"g1 Name": "PM"},
    }
    rows = svc.parse_gun_raw(SOURCE_JSON_API, envelope)
    assert len(rows) == 1
    assert rows[0]["name"] == "PM"
    assert rows[0]["weapon_class"] == "handgun"


def test_parse_graphql_guns_errors():
    with pytest.raises(svc.TarkovGunError):
        svc.parse_graphql_guns({"errors": ["down"]})


def test_download_graphql_guns(monkeypatch: pytest.MonkeyPatch):
    def fake_http(url, *, method="GET", body=None, headers=None, timeout=120):  # noqa: ANN001
        assert method == "POST"
        return json.dumps(
            {
                "data": {
                    "items": [
                        {
                            "id": "g",
                            "name": "Gun",
                            "shortName": "G",
                            "types": ["gun"],
                            "categories": [
                                {
                                    "id": "5447b5f14bdc2d61278b4567",
                                    "normalizedName": "assault-rifle",
                                }
                            ],
                            "properties": {
                                "__typename": "ItemPropertiesWeapon",
                                "caliber": "5.56x45mm",
                                "fireRate": 800,
                                "ergonomics": 50,
                                "recoilVertical": 70,
                                "recoilHorizontal": 200,
                                "effectiveDistance": 500,
                                "fireModes": ["single"],
                                "defaultAmmo": {"id": "a"},
                                "allowedAmmo": [{"id": "a"}],
                            },
                        }
                    ]
                }
            }
        ).encode()

    monkeypatch.setattr(svc, "_http_request", fake_http)
    bundle = svc.download_graphql_guns(lang="zh")
    assert bundle.source == SOURCE_GRAPHQL
    rows = svc.parse_gun_raw(bundle.source, bundle.payload)
    assert len(rows) == 1
