"""Unit tests for tarkov ammo sync parsers / normalize."""

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
    assert svc.normalize_caliber("") == "未知"


def test_parse_graphql_ammo():
    payload = {
        "data": {
            "ammo": [
                {
                    "caliber": "5.45x39mm",
                    "damage": 40,
                    "penetrationPower": 51,
                    "armorDamage": 57,
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
    assert rows[0]["penetration"] == 51
    assert rows[0]["damage"] == 40


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
                        "damage": 54,
                        "penetrationPower": 31,
                        "armorDamage": 37,
                    },
                },
                "gun": {
                    "id": "gun",
                    "properties": {"propertiesType": "ItemPropertiesWeapon"},
                },
            }
        }
    }
    locale = {
        "54527a984bdc2d4e668b4567 Name": "5.56x45mm M855",
        "54527a984bdc2d4e668b4567 ShortName": "M855",
    }
    rows = svc.parse_json_api_ammo(payload, locale=locale)
    assert len(rows) == 1
    assert rows[0]["short_name"] == "M855"
    assert rows[0]["caliber"] == "5.56x45mm"
    assert rows[0]["penetration"] == 31


def test_sync_prefers_json_api_over_tarkovdata(monkeypatch: pytest.MonkeyPatch):
    class FakeSession:
        def __init__(self):
            self.added = []
            self.committed = False

        def query(self, model):  # noqa: ANN001
            class Q:
                def delete(self_inner):  # noqa: N805
                    return None

                def filter(self_inner, *_a, **_k):  # noqa: N805
                    return self_inner

                def one_or_none(self_inner):  # noqa: N805
                    return None

            return Q()

        def add(self, obj):  # noqa: ANN001
            self.added.append(obj)

        def commit(self):
            self.committed = True

    monkeypatch.setattr(
        svc,
        "fetch_ammo_from_graphql",
        lambda **_k: (_ for _ in ()).throw(svc.TarkovAmmoError("graphql down")),
    )
    monkeypatch.setattr(
        svc,
        "fetch_ammo_from_json_api",
        lambda **_k: [
            {
                "item_id": "j1",
                "name": "JSON Ammo",
                "short_name": "JA",
                "caliber": "5.45x39mm",
                "damage": 40,
                "penetration": 50,
                "armor_damage": 55,
            }
        ],
    )
    monkeypatch.setattr(
        svc,
        "fetch_ammo_from_tarkovdata",
        lambda: (_ for _ in ()).throw(AssertionError("should not call tarkovdata")),
    )
    monkeypatch.setattr(svc, "get_ammo_meta", lambda _db: None)

    db = FakeSession()
    result = svc.sync_from_upstream(db)
    assert result["source"] == "json.tarkov.dev"
    assert result["ammo_count"] == 1


def test_fetch_ammo_from_graphql_posts_json(monkeypatch: pytest.MonkeyPatch):
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
    rows = svc.fetch_ammo_from_graphql(lang="zh")
    assert captured["method"] == "POST"
    assert captured["url"] == svc.TARKOV_GRAPHQL_URL
    payload = json.loads(captured["body"].decode())
    assert payload["variables"]["lang"] == "zh"
    assert len(rows) == 1
