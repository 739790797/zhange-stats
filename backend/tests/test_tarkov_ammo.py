"""Unit tests for tarkov ammo parsers."""

from __future__ import annotations

import json

import pytest

from app.services import tarkov_ammo as svc


def test_normalize_caliber():
    assert svc.normalize_caliber("Caliber545x39") == "5.45x39mm"
    assert svc.normalize_caliber("5.45x39mm") == "5.45x39mm"
    assert svc.normalize_caliber("Caliber9x19PARA") == "9x19mm"
    assert svc.normalize_caliber("Caliber1143x23ACP") == ".45 ACP"
    assert svc.normalize_caliber("Caliber46x30") == "4.6x30mm"
    assert svc.normalize_caliber("Caliber127x108") == "12.7x108mm"
    assert svc.normalize_caliber("Caliber26x75") == "26x75mm"
    assert svc.normalize_caliber("Caliber58x42") == "5.8x42mm"
    assert svc.normalize_caliber("Caliber68x51") == "6.8x51mm"
    assert svc.normalize_caliber("Caliber725") == "72.5mm"
    assert svc.normalize_caliber("Caliber127x99") == ".50 BMG"
    assert svc.normalize_caliber("Caliber784x49") == ".308 Marlin Express"
    assert svc.normalize_caliber("Caliber999x99") == "999x99"
    assert svc.normalize_caliber("") == ""


def test_parse_graphql_ammo():
    payload = {
        "data": {
            "ammo": [
                {
                    "caliber": "5.45x39mm",
                    "damage": 40,
                    "penetrationPower": 51,
                    "armorDamage": 57,
                    "ammoType": "bullet",
                    "initialSpeed": 830,
                    "accuracyModifier": 0.05,
                    "recoilModifier": -0.1,
                    "lightBleedModifier": 0.2,
                    "heavyBleedModifier": 0.1,
                    "item": {
                        "id": "56dff4ecd2720b5d7b8b456b",
                        "name": "5.45x39mm BS gs",
                        "shortName": "BS",
                    },
                }
            ]
        }
    }
    rows = svc.parse_graphql_ammo(payload)
    assert len(rows) == 1
    assert rows[0]["item_id"] == "56dff4ecd2720b5d7b8b456b"
    assert rows[0]["caliber"] == "5.45x39mm"
    assert rows[0]["ammo_type"] == "bullet"
    assert rows[0]["penetration"] == 51
    assert rows[0]["damage"] == 40
    assert rows[0]["initial_speed"] == 830
    assert rows[0]["accuracy_modifier"] == pytest.approx(0.05)
    assert rows[0]["recoil_modifier"] == pytest.approx(-0.1)
    assert rows[0]["light_bleed_modifier"] == pytest.approx(0.2)
    assert rows[0]["heavy_bleed_modifier"] == pytest.approx(0.1)


def test_parse_graphql_ammo_errors():
    with pytest.raises(svc.TarkovAmmoError):
        svc.parse_graphql_ammo({"errors": ["GraphQL server unavailable"]})


def test_parse_tarkovdata_ammo():
    table = {
        "56dff4ecd2720b5d7b8b456b": {
            "id": "56dff4ecd2720b5d7b8b456b",
            "name": "5.45x39mm BS gs",
            "shortName": "BS",
            "caliber": "Caliber545x39",
            "ballistics": {
                "damage": 40,
                "penetrationPower": 51,
                "armorDamage": 57,
            },
        }
    }
    rows = svc.parse_tarkovdata_ammo(table)
    assert len(rows) == 1
    assert rows[0]["caliber"] == "5.45x39mm"
    assert rows[0]["short_name"] == "BS"


def test_parse_json_api_ammo():
    payload = {
        "data": {
            "items": {
                "54527a984bdc2d4e668b4567": {
                    "id": "54527a984bdc2d4e668b4567",
                    "name": "54527a984bdc2d4e668b4567 Name",
                    "shortName": "54527a984bdc2d4e668b4567 ShortName",
                    "types": ["ammo"],
                    "properties": {
                        "propertiesType": "ItemPropertiesAmmo",
                        "caliber": "Caliber556x45NATO",
                        "ammoType": "bullet",
                        "damage": 54,
                        "penetrationPower": 31,
                        "armorDamage": 37,
                        "initialSpeed": 922,
                        "accuracyModifier": 0,
                        "recoilModifier": 0,
                        "lightBleedModifier": 0,
                        "heavyBleedModifier": 0,
                    },
                }
            }
        }
    }
    locale = {
        "54527a984bdc2d4e668b4567 Name": "5.56x45mm M855",
        "54527a984bdc2d4e668b4567 ShortName": "M855",
    }
    rows = svc.parse_json_api_ammo(payload, locale=locale)
    assert len(rows) == 1
    assert rows[0]["name"] == "5.56x45mm M855"
    assert rows[0]["short_name"] == "M855"
    assert rows[0]["caliber"] == "5.56x45mm"
    assert rows[0]["initial_speed"] == 922


def test_download_graphql_ammo_posts_json(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake_http(url, *, method="GET", body=None, headers=None, timeout=120):  # noqa: ANN001
        captured["url"] = url
        captured["method"] = method
        captured["body"] = body
        captured["headers"] = headers
        return json.dumps(
            {
                "data": {
                    "ammo": [
                        {
                            "caliber": "9x19mm",
                            "damage": 50,
                            "penetrationPower": 20,
                            "armorDamage": 27,
                            "item": {"id": "a", "name": "PST", "shortName": "PST"},
                        }
                    ]
                }
            }
        ).encode()

    monkeypatch.setattr(svc, "_http_request", fake_http)
    bundle = svc.download_graphql_ammo(lang="zh")
    assert captured["method"] == "POST"
    assert captured["url"] == svc.TARKOV_GRAPHQL_URL
    payload = json.loads(captured["body"].decode())
    assert payload["variables"]["lang"] == "zh"
    assert bundle.source == svc.SOURCE_GRAPHQL
    rows = svc.parse_ammo_raw(bundle.source, bundle.payload)
    assert len(rows) == 1
