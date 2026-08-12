"""Unit tests for tarkov ammo sync parsers / raw persist."""

from __future__ import annotations

import json

import pytest

from app.models.tarkov import TarkovAmmo, TarkovAmmoMeta, TarkovAmmoRaw
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
    # 未收录：只剥前缀，不猜小数点
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
    assert rows[0]["ammo_type"] == "bullet"
    assert rows[0]["penetration"] == 31


def test_parse_ammo_raw_json_envelope():
    envelope = {
        "items": {
            "data": {
                "items": {
                    "a1": {
                        "id": "a1",
                        "name": "a1 Name",
                        "shortName": "a1 ShortName",
                        "properties": {
                            "propertiesType": "ItemPropertiesAmmo",
                            "caliber": "Caliber545x39",
                            "damage": 40,
                            "penetrationPower": 50,
                            "armorDamage": 55,
                        },
                    }
                }
            }
        },
        "locale": {
            "a1 Name": "5.45 BT",
            "a1 ShortName": "BT",
        },
    }
    rows = svc.parse_ammo_raw(svc.SOURCE_JSON_API, envelope)
    assert len(rows) == 1
    assert rows[0]["short_name"] == "BT"
    assert rows[0]["caliber"] == "5.45x39mm"


class _FakeQuery:
    def __init__(self, session: "FakeSession", model):  # noqa: ANN001
        self._session = session
        self._model = model

    def delete(self):
        self._session.store[self._model] = []

    def filter(self, *_a, **_k):  # noqa: ANN001
        return self

    def order_by(self, *_a, **_k):  # noqa: ANN001
        return self

    def all(self):
        return list(self._session.store.get(self._model) or [])

    def one_or_none(self):
        rows = self._session.store.get(self._model) or []
        return rows[0] if rows else None

    def count(self):
        return len(self._session.store.get(self._model) or [])


class FakeSession:
    def __init__(self):
        self.store: dict[type, list] = {
            TarkovAmmo: [],
            TarkovAmmoMeta: [],
            TarkovAmmoRaw: [],
        }
        self.committed = False

    def query(self, model):  # noqa: ANN001
        return _FakeQuery(self, model)

    def add(self, obj):  # noqa: ANN001
        bucket = self.store.setdefault(type(obj), [])
        # upsert singleton raw/meta by replacing same id
        if isinstance(obj, (TarkovAmmoRaw, TarkovAmmoMeta)):
            bucket[:] = [x for x in bucket if getattr(x, "id", None) != obj.id]
        bucket.append(obj)

    def commit(self):
        self.committed = True


def test_sync_persists_raw_then_derived(monkeypatch: pytest.MonkeyPatch):
    items_body = {
        "data": {
            "items": {
                "j1": {
                    "id": "j1",
                    "name": "JSON Ammo",
                    "shortName": "JA",
                    "properties": {
                        "propertiesType": "ItemPropertiesAmmo",
                        "caliber": "Caliber545x39",
                        "damage": 40,
                        "penetrationPower": 50,
                        "armorDamage": 55,
                    },
                }
            }
        }
    }

    monkeypatch.setattr(
        svc,
        "download_graphql_ammo",
        lambda **_k: (_ for _ in ()).throw(svc.TarkovAmmoError("graphql down")),
    )
    monkeypatch.setattr(
        svc,
        "download_json_api_ammo",
        lambda **_k: svc.AmmoUpstreamBundle(
            source=svc.SOURCE_JSON_API,
            payload={"items": items_body, "locale": None},
            note="json.tarkov.dev/regular/items",
        ),
    )
    monkeypatch.setattr(
        svc,
        "download_tarkovdata_ammo",
        lambda: (_ for _ in ()).throw(AssertionError("should not call tarkovdata")),
    )

    db = FakeSession()
    result = svc.sync_from_upstream(db)
    assert result["source"] == svc.SOURCE_JSON_API
    assert result["ammo_count"] == 1
    assert db.committed is True

    raws = db.store[TarkovAmmoRaw]
    assert len(raws) == 1
    assert raws[0].source == svc.SOURCE_JSON_API
    stored = json.loads(raws[0].raw_json)
    assert "items" in stored

    ammos = db.store[TarkovAmmo]
    assert len(ammos) == 1
    assert ammos[0].item_id == "j1"

    metas = db.store[TarkovAmmoMeta]
    assert len(metas) == 1
    assert metas[0].ammo_count == 1


def test_rebuild_ammo_from_raw(monkeypatch: pytest.MonkeyPatch):
    _ = monkeypatch
    db = FakeSession()
    payload = {
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
    db.add(
        TarkovAmmoRaw(
            id=svc.RAW_ROW_ID,
            source=svc.SOURCE_GRAPHQL,
            raw_json=json.dumps(payload, ensure_ascii=False),
            synced_at=svc.now_naive(),
            note="saved",
        )
    )

    result = svc.rebuild_ammo_from_raw(db)
    assert result["ammo_count"] == 1
    assert result["source"] == svc.SOURCE_GRAPHQL
    assert len(db.store[TarkovAmmo]) == 1
    assert db.store[TarkovAmmo][0].short_name == "PST"


def test_ensure_ammo_rebuilds_from_raw_before_upstream(monkeypatch: pytest.MonkeyPatch):
    db = FakeSession()
    payload = {
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
    db.add(
        TarkovAmmoRaw(
            id=svc.RAW_ROW_ID,
            source=svc.SOURCE_GRAPHQL,
            raw_json=json.dumps(payload, ensure_ascii=False),
            synced_at=svc.now_naive(),
            note="saved",
        )
    )

    def boom():
        raise AssertionError("should not sync upstream")

    monkeypatch.setattr(svc, "sync_from_upstream", boom)
    rows = svc.ensure_ammo(db)
    assert len(rows) == 1


def test_failed_sync_does_not_call_persist(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    monkeypatch.setattr(
        svc,
        "download_graphql_ammo",
        lambda **_k: (_ for _ in ()).throw(svc.TarkovAmmoError("g")),
    )
    monkeypatch.setattr(
        svc,
        "download_json_api_ammo",
        lambda **_k: (_ for _ in ()).throw(svc.TarkovAmmoError("j")),
    )
    monkeypatch.setattr(
        svc,
        "download_tarkovdata_ammo",
        lambda: (_ for _ in ()).throw(svc.TarkovAmmoError("t")),
    )

    def persist(_db, _bundle):  # noqa: ANN001
        calls.append("persist")
        return {}

    monkeypatch.setattr(svc, "persist_ammo_bundle", persist)
    with pytest.raises(svc.TarkovAmmoError):
        svc.sync_from_upstream(FakeSession())
    assert calls == []


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
