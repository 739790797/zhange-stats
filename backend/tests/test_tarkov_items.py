"""Unit tests for shared tarkov items sync."""

from __future__ import annotations

import json

import pytest

from app.models.tarkov import (
    TarkovAmmo,
    TarkovAmmoMeta,
    TarkovGun,
    TarkovGunMeta,
    TarkovItemsMeta,
    TarkovItemsRaw,
)
from app.services import tarkov_ammo as ammo_svc
from app.services import tarkov_guns as gun_svc
from app.services import tarkov_items as svc
from app.services.tarkov_ammo import SOURCE_GRAPHQL, SOURCE_JSON_API


class _FakeQuery:
    def __init__(self, session, model):  # noqa: ANN001
        self.session = session
        self.model = model
        self._rows = list(session.store.get(model, []))

    def filter(self, *args, **_k):  # noqa: ANN001
        # Support TarkovAmmo.icon_link != ""
        if args:
            expr = args[0]
            left = getattr(expr, "left", None)
            key = getattr(left, "key", None) or getattr(left, "name", None)
            if key == "icon_link":
                self._rows = [
                    r for r in self._rows if str(getattr(r, "icon_link", "") or "")
                ]
        return self

    def order_by(self, *_a, **_k):  # noqa: ANN001
        return self

    def count(self):
        return len(self._rows)

    def delete(self):
        self.session.store[self.model] = []
        self._rows = []

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class FakeSession:
    def __init__(self):
        self.store: dict = {
            TarkovAmmo: [],
            TarkovAmmoMeta: [],
            TarkovGun: [],
            TarkovGunMeta: [],
            TarkovItemsRaw: [],
            TarkovItemsMeta: [],
        }
        self.committed = False

    def query(self, model):  # noqa: ANN001
        return _FakeQuery(self, model)

    def add(self, obj):  # noqa: ANN001
        bucket = self.store.setdefault(type(obj), [])
        if isinstance(
            obj, (TarkovItemsRaw, TarkovItemsMeta, TarkovAmmoMeta, TarkovGunMeta)
        ):
            bucket[:] = [x for x in bucket if getattr(x, "id", None) != obj.id]
        bucket.append(obj)

    def commit(self):
        self.committed = True


def _json_envelope() -> dict:
    return {
        "items": {
            "data": {
                "items": {
                    "ammo1": {
                        "id": "ammo1",
                        "name": "ammo1 Name",
                        "shortName": "ammo1 ShortName",
                        "types": ["ammo"],
                        "properties": {
                            "propertiesType": "ItemPropertiesAmmo",
                            "caliber": "Caliber545x39",
                            "ammoType": "bullet",
                            "damage": 40,
                            "penetrationPower": 50,
                            "armorDamage": 55,
                        },
                    },
                    "gun1": {
                        "id": "gun1",
                        "name": "gun1 Name",
                        "shortName": "gun1 ShortName",
                        "types": ["gun"],
                        "categories": ["5447b5f14bdc2d61278b4567"],
                        "properties": {
                            "propertiesType": "ItemPropertiesWeapon",
                            "caliber": "Caliber545x39",
                            "fireRate": 650,
                            "ergonomics": 30,
                            "recoilVertical": 90,
                            "recoilHorizontal": 200,
                            "effectiveDistance": 500,
                            "fireModes": ["single"],
                            "defaultAmmo": "ammo1",
                            "allowedAmmo": ["ammo1"],
                        },
                    },
                },
                "itemCategories": {
                    "5447b5f14bdc2d61278b4567": {"normalizedName": "assault-rifle"},
                },
            }
        },
        "locale": {
            "ammo1 Name": "5.45 BS",
            "ammo1 ShortName": "BS",
            "gun1 Name": "AK-74N",
            "gun1 ShortName": "AK-74N",
        },
    }


def test_parse_json_items_both():
    ammo_rows, gun_rows = svc.parse_items_payload(SOURCE_JSON_API, _json_envelope())
    assert len(ammo_rows) == 1
    assert len(gun_rows) == 1
    assert ammo_rows[0]["item_id"] == "ammo1"
    assert gun_rows[0]["item_id"] == "gun1"


def test_sync_json_once_writes_both(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        svc,
        "download_graphql_items",
        lambda **_k: (_ for _ in ()).throw(svc.TarkovItemsError("graphql down")),
    )
    monkeypatch.setattr(
        svc,
        "download_json_api_items",
        lambda **_k: svc.ItemsUpstreamBundle(
            source=SOURCE_JSON_API,
            payload=_json_envelope(),
            note="json.tarkov.dev/regular/items",
        ),
    )

    db = FakeSession()
    result = svc.sync_from_upstream(db)
    assert result["ammo_count"] == 1
    assert result["gun_count"] == 1
    assert db.committed is True
    assert len(db.store[TarkovItemsRaw]) == 1
    assert len(db.store[TarkovAmmo]) == 1
    assert len(db.store[TarkovGun]) == 1


def test_ensure_items_rebuilds_once(monkeypatch: pytest.MonkeyPatch):
    db = FakeSession()
    payload = {
        "format": svc.GRAPHQL_SPLIT_FORMAT,
        "ammo": {
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
        },
        "guns": {
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
        },
    }
    db.add(
        TarkovItemsRaw(
            id=svc.RAW_ROW_ID,
            source=SOURCE_GRAPHQL,
            raw_json=json.dumps(payload, ensure_ascii=False),
            synced_at=__import__("datetime").datetime.utcnow(),
            note="saved",
        )
    )

    calls = {"sync": 0}

    def boom(_db=None):  # noqa: ANN001
        calls["sync"] += 1
        raise AssertionError("should not sync upstream")

    monkeypatch.setattr(svc, "sync_from_upstream", boom)
    svc.ensure_items(db)
    assert calls["sync"] == 0
    assert len(db.store[TarkovAmmo]) == 1
    assert len(db.store[TarkovGun]) == 1

    # second ensure: both derived filled → no rebuild needed beyond count check
    svc.ensure_items(db)


def test_ensure_ammo_and_guns_share_sync(monkeypatch: pytest.MonkeyPatch):
    calls = {"n": 0}

    def fake_sync(db):  # noqa: ANN001
        calls["n"] += 1
        now = __import__("datetime").datetime.utcnow()
        ammo_svc.replace_derived_ammo_rows(
            db,
            [
                {
                    "item_id": "a",
                    "name": "A",
                    "short_name": "A",
                    "caliber": "9x19mm",
                    "ammo_type": "bullet",
                    "damage": 1,
                    "penetration": 1,
                    "armor_damage": 1,
                }
            ],
            source=SOURCE_JSON_API,
            note="t",
            synced_at=now,
        )
        gun_svc.replace_derived_gun_rows(
            db,
            [
                {
                    "item_id": "g",
                    "name": "G",
                    "short_name": "G",
                    "caliber": "5.56x45mm",
                    "weapon_class": "assault-rifle",
                    "fire_rate": 1,
                    "ergonomics": 1.0,
                    "recoil_vertical": 1,
                    "recoil_horizontal": 1,
                    "effective_distance": 1,
                    "fire_modes": ["single"],
                    "default_ammo_id": "a",
                    "allowed_ammo_ids": ["a"],
                    "icon_link": "",
                }
            ],
            source=SOURCE_JSON_API,
            note="t",
            synced_at=now,
        )
        db.commit()
        return {"ammo_count": 1, "gun_count": 1, "source": SOURCE_JSON_API}

    monkeypatch.setattr(svc, "sync_from_upstream", fake_sync)
    monkeypatch.setattr(svc, "get_items_raw", lambda _db: None)

    db = FakeSession()
    ammo_svc.ensure_ammo(db)
    gun_svc.ensure_guns(db)
    assert calls["n"] == 1
