"""塔科夫 raw 解析缓存：命中只看表头、不读 raw_json；PVP / PVE 各留一份；详情走 ETag。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.guides import tarkov as tarkov_api
from app.core.database import Base, get_db
from app.core.http_cache import CATALOG_CACHE_CONTROL
from app.services.tarkov import catalog as catalog_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov import overlay as overlay_svc
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import upstream as upstream_svc
from app.services.tarkov.ammo import SOURCE_GRAPHQL, SOURCE_JSON_API
from app.services.tarkov.game_mode import game_mode_scope
from app.services.tarkov.items import GRAPHQL_SPLIT_FORMAT
from app.services.tarkov.parse_cache import ModeCache, ModeKeyedCache

PRAPOR = "54cb50c76803fa8b248b4571"
CUSTOMS = "56f40101d2720b2a4d8b45d6"
WOODS = "5704e3c2d2720bac5b8b4567"

_CACHES = (
    catalog_svc._parsed_cache,
    catalog_svc._items_index_cache,
    catalog_svc._pack_index_cache,
    tasks_svc._parsed_cache,
    tasks_svc._raid_prep_cache,
    tasks_svc._raid_prep_index_cache,
)


def _reset_caches() -> None:
    for cache in _CACHES:
        cache.clear()
    items_svc._verified_raw.clear()


@pytest.fixture(autouse=True)
def _fresh_caches():
    _reset_caches()
    yield
    _reset_caches()


@pytest.fixture
def clock(monkeypatch):
    state = {"now": datetime(2026, 1, 1, 12, 0, 0)}

    def tick() -> datetime:
        state["now"] += timedelta(seconds=1)
        return state["now"]

    monkeypatch.setattr(upstream_svc, "now_naive", tick)
    return state


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'tarkov.db'}")
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class _SqlLog:
    def __init__(self, engine) -> None:  # noqa: ANN001
        self.engine = engine
        self.statements: list[str] = []

    def _record(self, _conn, _cursor, statement, *_a) -> None:  # noqa: ANN001
        self.statements.append(statement)

    def __enter__(self) -> list[str]:
        event.listen(self.engine, "before_cursor_execute", self._record)
        return self.statements

    def __exit__(self, *_exc) -> None:
        event.remove(self.engine, "before_cursor_execute", self._record)


def _no_decode(*_a, **_k):
    raise AssertionError("缓存命中不应再读 raw_json")


def _task(tid: str, map_id: str = CUSTOMS) -> dict:
    return {
        "id": tid,
        "name": tid,
        "trader": PRAPOR,
        "map": map_id,
        "objectives": [
            {"id": f"{tid}-o", "type": "visit", "description": "go", "maps": [map_id]},
        ],
        "experience": 100,
    }


def _items_dump(*ids: str) -> dict:
    return {
        "data": {
            "items": {
                ident: {
                    "id": ident,
                    "name": f"{ident} Name",
                    "shortName": ident.upper(),
                    "types": ["barter"],
                    "handbookCategories": {},
                    "properties": {},
                }
                for ident in ids
            }
        }
    }


def test_mode_cache_keeps_one_entry_per_mode() -> None:
    cache: ModeCache[str] = ModeCache()
    with game_mode_scope("pvp"):
        cache.put("k1", "pvp")
    with game_mode_scope("pve"):
        cache.put("k2", "pve")
    with game_mode_scope("pvp"):
        assert cache.get("k1") == "pvp"
        assert cache.get("k2") is None
        cache.put("k3", "pvp-new")
        assert cache.get("k1") is None
    with game_mode_scope("pve"):
        assert cache.get("k2") == "pve"
    cache.clear()
    with game_mode_scope("pvp"):
        assert cache.get("k3") is None


def test_mode_keyed_cache_drops_old_subkeys_on_new_key() -> None:
    cache: ModeKeyedCache[int] = ModeKeyedCache()
    with game_mode_scope("pvp"):
        cache.put("k1", "customs", 1)
        cache.put("k1", "woods", 2)
        assert (cache.get("k1", "customs"), cache.get("k1", "woods")) == (1, 2)
        cache.put("k2", "customs", 3)
        assert cache.get("k2", "customs") == 3
        assert cache.get("k2", "woods") is None
        assert cache.get("k1", "customs") is None
    with game_mode_scope("pve"):
        assert cache.get("k2", "customs") is None


def test_header_query_leaves_raw_json_unloaded(engine, db, clock) -> None:
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(
            db, "tasks", {"tasks": {"t1": _task("t1")}}, source="test", note="n"
        )
    fresh = sessionmaker(bind=engine)()
    try:
        with game_mode_scope("pvp"):
            with _SqlLog(engine) as header_sql:
                source, synced, _note = upstream_svc.raw_row_header(
                    upstream_svc.load_raw_row(fresh, "tasks")
                )
            with _SqlLog(engine) as json_sql:
                payload = upstream_svc.load_raw(fresh, "tasks")
    finally:
        fresh.close()
    assert (source, synced) == ("test", "2026-01-01T12:00:01")
    assert header_sql and not any("raw_json" in sql for sql in header_sql)
    assert any("raw_json" in sql for sql in json_sql)
    assert payload["tasks"]["t1"]["id"] == "t1"


def test_overlay_token_memo_lasts_one_transaction(engine, db, clock) -> None:
    other = sessionmaker(bind=engine)()
    try:
        with game_mode_scope("pvp"):
            overlay_svc.persist_overlay(db, {"tasks": {}})
            first = overlay_svc.overlay_cache_token(db)
            with _SqlLog(engine) as sql:
                assert overlay_svc.overlay_cache_token(db) == first
            assert sql == []
            overlay_svc.persist_overlay(other, {"tasks": {"t1": {"disabled": True}}})
            db.commit()
            second = overlay_svc.overlay_cache_token(db)
    finally:
        other.close()
    assert first == "2026-01-01T12:00:01"
    assert second == "2026-01-01T12:00:02"


def test_parsed_tasks_hit_by_header_per_mode(db, clock, monkeypatch) -> None:
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(db, "tasks", {"tasks": {"p1": _task("p1")}}, source="test", note="pvp")
    with game_mode_scope("pve"):
        upstream_svc.persist_raw(db, "tasks", {"tasks": {"e1": _task("e1")}}, source="test", note="pve")
    with game_mode_scope("pvp"):
        pvp_rows = tasks_svc.load_parsed_tasks(db)[1]
    with game_mode_scope("pve"):
        pve_rows = tasks_svc.load_parsed_tasks(db)[1]
    assert [row["id"] for row in pvp_rows] == ["p1"]
    assert [row["id"] for row in pve_rows] == ["e1"]

    real_load = tasks_svc._load_payload
    monkeypatch.setattr(tasks_svc, "_load_payload", _no_decode)
    with game_mode_scope("pvp"):
        assert tasks_svc.load_parsed_tasks(db)[1] is pvp_rows
    with game_mode_scope("pve"):
        assert tasks_svc.load_parsed_tasks(db)[1] is pve_rows

    monkeypatch.setattr(tasks_svc, "_load_payload", real_load)
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(db, "tasks", {"tasks": {"p2": _task("p2")}}, source="test", note="pvp")
        assert [row["id"] for row in tasks_svc.load_parsed_tasks(db)[1]] == ["p2"]


def test_raid_prep_rows_cached_per_map(db, clock, monkeypatch) -> None:
    payload = {"tasks": {"c1": _task("c1", CUSTOMS), "w1": _task("w1", WOODS)}}
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(db, "tasks", payload, source="test", note="n")
        customs = tasks_svc.load_raid_prep_rows(db, "customs")
        woods = tasks_svc.load_raid_prep_rows(db, "woods")
        monkeypatch.setattr(tasks_svc, "_load_payload", _no_decode)
        assert tasks_svc.load_raid_prep_rows(db, "customs")[2] is customs[2]
        assert tasks_svc.load_raid_prep_rows(db, "woods")[2] is woods[2]
        assert tasks_svc.raid_prep_task_ids_for_map(db, "customs") == {"c1", "w1"}
    on_map = {
        slug: {row["id"]: row["on_this_map"] for row in rows[2]}
        for slug, rows in (("customs", customs), ("woods", woods))
    }
    assert on_map == {
        "customs": {"c1": True, "w1": False},
        "woods": {"c1": False, "w1": True},
    }


def test_catalog_and_items_index_hit_by_header_per_mode(db, clock, monkeypatch) -> None:
    monkeypatch.setattr(items_svc, "ensure_items", lambda _db: None)
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(db, "items", _items_dump("a1"), source=SOURCE_JSON_API, note="pvp")
    with game_mode_scope("pve"):
        upstream_svc.persist_raw(
            db, "items", _items_dump("b1", "b2"), source=SOURCE_JSON_API, note="pve"
        )
    with game_mode_scope("pvp"):
        pvp_catalog = catalog_svc.load_parsed_catalog(db)
        pvp_index = catalog_svc.load_items_index(db)
    with game_mode_scope("pve"):
        pve_catalog = catalog_svc.load_parsed_catalog(db)
        pve_index = catalog_svc.load_items_index(db)

    monkeypatch.setattr(catalog_svc, "_read_payload", _no_decode)
    monkeypatch.setattr(catalog_svc, "_load_payload", _no_decode)
    with game_mode_scope("pvp"):
        assert catalog_svc.load_parsed_catalog(db) is pvp_catalog
        assert catalog_svc.load_items_index(db) is pvp_index
        assert catalog_svc.peek_items_index(db) is pvp_index
    with game_mode_scope("pve"):
        assert catalog_svc.load_parsed_catalog(db) is pve_catalog
        assert catalog_svc.load_items_index(db) is pve_index
    assert {row["id"] for row in pvp_catalog[1]} == {"a1"}
    assert set(pve_index) == {"b1", "b2"}
    assert pvp_index.full and pvp_index.source == SOURCE_JSON_API


def test_peek_items_index_without_raw_is_none(db) -> None:
    with game_mode_scope("pvp"):
        assert catalog_svc.peek_items_index(db) is None


def test_ensure_items_checks_derived_tables_once_per_raw(monkeypatch) -> None:
    class _Raw:
        source = SOURCE_JSON_API

        def __init__(self) -> None:
            self.synced_at = datetime(2026, 1, 1)

    raw = _Raw()
    checks: list[str] = []
    monkeypatch.setattr(items_svc, "get_items_raw", lambda _db: raw)
    monkeypatch.setattr(
        items_svc,
        "_derived_gaps",
        lambda _db, _raw: checks.append("check") or (False, False),
    )
    with game_mode_scope("pvp"):
        items_svc.ensure_items(None)  # type: ignore[arg-type]
        items_svc.ensure_items(None)  # type: ignore[arg-type]
    assert len(checks) == 1
    raw.synced_at = datetime(2026, 1, 2)
    with game_mode_scope("pvp"):
        items_svc.ensure_items(None)  # type: ignore[arg-type]
    with game_mode_scope("pve"):
        items_svc.ensure_items(None)  # type: ignore[arg-type]
    assert len(checks) == 3


def _rich_items_payload() -> dict:
    return {
        "items": {
            "data": {
                "items": {
                    "gun1": {
                        "id": "gun1",
                        "name": "gun1 Name",
                        "shortName": "G",
                        "types": ["gun"],
                        "categories": ["5447b5f14bdc2d61278b4567"],
                        "handbookCategories": ["5b5f78fc86f77409407a7f90"],
                        "containsItems": [{"item": "ammo1", "count": 30}],
                        "conflictingItems": ["plate1"],
                        "properties": {
                            "propertiesType": "ItemPropertiesWeapon",
                            "defaultAmmo": "ammo1",
                            "allowedAmmo": ["ammo1"],
                            "defaultPreset": "preset1",
                            "presets": ["preset1"],
                            "armorSlots": [{"name": "Front", "allowedPlates": ["plate1"]}],
                        },
                    },
                    "ammo1": {"id": "ammo1", "types": ["ammo"]},
                    "preset1": {
                        "id": "preset1",
                        "types": ["preset"],
                        "containsItems": [{"item": "plate1", "count": 1}],
                        "properties": {"default": True, "baseItem": "gun1"},
                    },
                    "plate1": {
                        "id": "plate1",
                        "types": ["armorPlate"],
                        "properties": {"class": 4, "durability": 40},
                    },
                },
                "itemCategories": {
                    "5447b5f14bdc2d61278b4567": {"normalizedName": "assault-rifle"}
                },
                "handbookCategories": {
                    "5b5f78fc86f77409407a7f90": {"normalizedName": "assault-rifles"}
                },
            }
        },
        "locale": {
            "gun1 Name": "MCX",
            "ammo1 Name": ".300 BPZ FMJ",
            "preset1 Name": "MCX 默认",
            "plate1 Name": "SAPI",
            "5447b5f14bdc2d61278b4567 Name": "突击步枪",
        },
    }


def test_items_index_detail_matches_full_payload_detail() -> None:
    payload = _rich_items_payload()
    index = catalog_svc.ItemsIndex(SOURCE_JSON_API, payload, "2026-01-01T00:00:00", "n")
    assert index.full
    assert set(index) == {"gun1", "ammo1", "preset1", "plate1"}
    for item_id in index:
        assert catalog_svc._item_detail(
            item_id, index, index.catalogs, index.locale
        ) == catalog_svc.extract_item_detail(SOURCE_JSON_API, payload, item_id)
    copy = index["gun1"]
    copy["name"] = "changed"
    assert index["gun1"]["name"] == "gun1 Name"
    assert index.get("missing") is None


def test_items_index_marks_graphql_split_as_partial() -> None:
    payload = {
        "format": GRAPHQL_SPLIT_FORMAT,
        "ammo": {"data": {"ammo": [{"item": {"id": "ammo1", "name": "BP"}, "damage": 40}]}},
        "guns": {"data": {"items": []}},
    }
    index = catalog_svc.ItemsIndex(SOURCE_GRAPHQL, payload, None, None)
    assert not index.full
    assert index["ammo1"]["properties"] == {"damage": 40}


def test_item_detail_etag_parts_follow_related_raws(db, clock, monkeypatch) -> None:
    monkeypatch.setattr(items_svc, "ensure_items", lambda _db: None)
    seen: list[tuple[str, ...]] = []
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(db, "items", _items_dump("a1"), source=SOURCE_JSON_API, note="n")
        seen.append(catalog_svc.item_detail_cache_parts(db))
        upstream_svc.persist_raw(db, "maps", {"data": {"maps": {}}}, source=SOURCE_JSON_API, note="n")
        seen.append(catalog_svc.item_detail_cache_parts(db))
        upstream_svc.persist_raw(db, "tasks", {"tasks": {}}, source="test", note="n")
        seen.append(catalog_svc.item_detail_cache_parts(db))
        upstream_svc.persist_raw(db, "barters", {"data": []}, source=SOURCE_JSON_API, note="n")
        seen.append(catalog_svc.item_detail_cache_parts(db))
        overlay_svc.persist_overlay(db, {"tasks": {}})
        seen.append(catalog_svc.item_detail_cache_parts(db))
        assert catalog_svc.item_detail_cache_parts(db) == seen[-1]
    assert len(set(seen)) == len(seen)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.core.platform_deps.is_feature_enabled", lambda _db, _feature: True)
    app = FastAPI()
    app.include_router(tarkov_api.router)
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as tc:
        yield tc


def test_item_detail_304_until_related_raw_changes(client, monkeypatch) -> None:
    parts = {"value": ("items-1", "maps-1", "", "||", "")}
    served: list[str] = []
    monkeypatch.setattr(catalog_svc, "item_detail_cache_parts", lambda _db: parts["value"])

    def fake_detail(_db, item_id: str) -> dict:  # noqa: ANN001
        if item_id == "nope":
            raise items_svc.TarkovItemsError(f"未找到物品: {item_id}")
        served.append(item_id)
        return {"id": item_id, "name": "钥匙", "source": SOURCE_JSON_API, "item": {}}

    monkeypatch.setattr(catalog_svc, "get_item_detail", fake_detail)
    first = client.get("/tarkov/items/k1")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert first.headers["cache-control"] == CATALOG_CACHE_CONTROL
    assert client.get("/tarkov/items/k1", headers={"If-None-Match": etag}).status_code == 304
    assert client.get("/tarkov/items/k2", headers={"If-None-Match": etag}).status_code == 200
    pve = client.get("/tarkov/items/k1?game_mode=pve", headers={"If-None-Match": etag})
    assert pve.status_code == 200
    parts["value"] = ("items-1", "maps-2", "", "||", "")
    changed = client.get("/tarkov/items/k1", headers={"If-None-Match": etag})
    assert changed.status_code == 200
    assert changed.headers["etag"] != etag
    missing = client.get("/tarkov/items/nope")
    assert missing.status_code == 404
    assert "etag" not in missing.headers
    assert served == ["k1", "k2", "k1", "k1"]


def test_ammo_detail_304_until_items_or_overlay_change(client, monkeypatch) -> None:
    token = {"value": "o1"}
    served: list[str] = []
    monkeypatch.setattr(items_svc, "ensure_items", lambda _db: None)
    monkeypatch.setattr(
        items_svc, "items_raw_header", lambda _db: (SOURCE_JSON_API, "s1", None)
    )
    monkeypatch.setattr(overlay_svc, "overlay_cache_token", lambda _db: token["value"])
    monkeypatch.setattr(
        items_svc,
        "get_ammo_item_detail",
        lambda _db, item_id: served.append(item_id)
        or {"id": item_id, "name": "BP", "item": {}, "properties": {}},
    )
    first = client.get("/tarkov/ammo/a1")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert client.get("/tarkov/ammo/a1", headers={"If-None-Match": etag}).status_code == 304
    token["value"] = "o2"
    assert client.get("/tarkov/ammo/a1", headers={"If-None-Match": etag}).status_code == 200
    assert served == ["a1", "a1"]
