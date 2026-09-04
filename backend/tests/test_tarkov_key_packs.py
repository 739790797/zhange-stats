"""钥匙分包：门锁按母图归包，不打真实上游。"""

from __future__ import annotations

import pytest

from app.services.tarkov.bosses import MAP_ZH
from app.services.tarkov.key_packs import (
    COMMUNITY_KEY_MAPS,
    SOURCE_JSON,
    SOURCE_STALE,
    TarkovKeyPacksError,
    UNAVAILABLE_MSG,
    attach_key_sources,
    attach_key_usage,
    build_key_source_index,
    build_key_usage_index,
    fetch_map_locks,
    group_key_packs,
    maps_have_lock_data,
    parse_json_maps_locks,
    parent_map_slug,
)

KEYS_ROOT = "5b47574386f77428ca22b342"


def _key(item_id: str, name: str) -> dict:
    return {"id": item_id, "name": name, "shortName": name, "iconLink": f"/{item_id}.png"}


def test_community_map_slugs_are_known() -> None:
    assert COMMUNITY_KEY_MAPS
    assert set(COMMUNITY_KEY_MAPS.values()) <= set(MAP_ZH)


def test_parent_map_slug_folds_variants() -> None:
    assert parent_map_slug("night-factory") == "factory"
    assert parent_map_slug("factory-night") == "factory"
    assert parent_map_slug("the-lab-dark") == "the-lab"
    assert parent_map_slug("ground-zero-21") == "ground-zero"
    assert parent_map_slug("streets") == "streets-of-tarkov"
    assert parent_map_slug("customs") == "customs"


def test_group_merges_variant_locks_into_parent() -> None:
    maps = [
        {
            "name": "工厂",
            "normalizedName": "factory",
            "locks": [{"key": _key("k-gate", "大门钥匙")}],
            "accessKeys": [],
        },
        {
            "name": "工厂（夜）",
            "normalizedName": "night-factory",
            "locks": [
                {"key": _key("k-gate", "大门钥匙")},
                {"key": _key("k-office", "办公室钥匙")},
            ],
            "accessKeys": [],
        },
    ]
    out = group_key_packs(maps, [])
    slugs = [row["slug"] for row in out["maps"]]
    assert slugs == ["factory"]
    pack = out["maps"][0]
    assert pack["name"] == "工厂"
    by_id = {row["id"]: row for row in pack["keys"]}
    assert by_id["k-gate"]["lock_count"] == 2
    assert by_id["k-office"]["lock_count"] == 1
    assert by_id["k-gate"]["name"] == "大门钥匙"
    assert by_id["k-gate"]["lock_types"] == []
    assert by_id["k-gate"]["needs_power"] is False


def test_group_keeps_multi_map_key_on_each_pack() -> None:
    maps = [
        {
            "name": "海关",
            "normalizedName": "customs",
            "locks": [{"key": _key("shared", "共用钥匙")}],
        },
        {
            "name": "森林",
            "normalizedName": "woods",
            "locks": [{"key": _key("shared", "共用钥匙")}],
        },
    ]
    out = group_key_packs(maps, [])
    by_slug = {row["slug"]: row for row in out["maps"]}
    assert {k["id"] for k in by_slug["customs"]["keys"]} == {"shared"}
    assert {k["id"] for k in by_slug["woods"]["keys"]} == {"shared"}


def test_group_marks_access_keys() -> None:
    maps = [
        {
            "name": "实验室",
            "normalizedName": "the-lab",
            "locks": [{"key": _key("k-lab", "实验室钥匙")}],
            "accessKeys": [_key("card", "实验室门禁卡")],
        }
    ]
    out = group_key_packs(maps, [])
    by_id = {row["id"]: row for row in out["maps"][0]["keys"]}
    assert by_id["card"]["access"] is True
    assert by_id["card"]["lock_count"] == 0
    assert by_id["k-lab"]["access"] is False
    assert by_id["k-lab"]["lock_count"] == 1


def test_group_catalog_name_wins_and_unbound_bucket() -> None:
    maps = [
        {
            "name": "海关",
            "normalizedName": "customs",
            "locks": [{"key": {"id": "dorm-114", "name": "Dorm 114"}}],
        }
    ]
    catalog = [
        {
            "id": "dorm-114",
            "name": "宿舍 114 钥匙",
            "short_name": "114",
            "icon_link": "/114.png",
            "types": ["keys"],
            "handbook_ids": [KEYS_ROOT],
            "properties": {"uses": 40},
        },
        {
            "id": "quest-only",
            "name": "任务专用钥",
            "short_name": "任务钥",
            "icon_link": "/q.png",
            "types": ["keys"],
            "handbook_ids": [KEYS_ROOT],
            "properties": {"uses": 0},
        },
        {
            "id": "not-a-key",
            "name": "绷带",
            "types": ["meds"],
            "handbook_ids": ["other"],
        },
    ]
    out = group_key_packs(maps, catalog)
    assert out["maps"][0]["keys"][0]["name"] == "宿舍 114 钥匙"
    assert out["maps"][0]["keys"][0]["short_name"] == "114"
    assert out["maps"][0]["keys"][0]["uses"] == 40
    assert out["maps"][0]["keys"][0]["description"] == ""
    assert [row["id"] for row in out["unbound"]] == ["quest-only"]
    assert out["unbound"][0]["name"] == "任务专用钥"
    assert out["unbound"][0]["uses"] == 0
    assert out["maps"][0]["keys"][0]["community"] is False
    assert out["unbound"][0]["community"] is False


def test_group_community_bind_second_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tarkov import key_packs as kp

    monkeypatch.setattr(kp, "COMMUNITY_KEY_MAPS", {"lonely": "icebreaker"})
    maps = [
        {
            "name": "海关",
            "normalizedName": "customs",
            "locks": [{"key": _key("dorm-114", "宿舍 114")}],
        }
    ]
    catalog = [
        {
            "id": "lonely",
            "name": "破冰船钥",
            "short_name": "冰钥",
            "icon_link": "/ice.png",
            "types": ["keys"],
            "handbook_ids": [KEYS_ROOT],
        },
        {
            "id": "dorm-114",
            "name": "宿舍 114 钥匙",
            "types": ["keys"],
            "handbook_ids": [KEYS_ROOT],
        },
    ]
    out = group_key_packs(maps, catalog)
    by_slug = {row["slug"]: row for row in out["maps"]}
    assert "lonely" not in {row["id"] for row in out["unbound"]}
    ice = by_slug["icebreaker"]
    assert ice["name"] == "破冰船"
    by_id = {row["id"]: row for row in ice["keys"]}
    assert by_id["lonely"]["community"] is True
    assert by_id["lonely"]["name"] == "破冰船钥"
    assert by_id["lonely"]["lock_count"] == 0
    assert by_slug["customs"]["keys"][0]["community"] is False


def test_group_community_does_not_override_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tarkov import key_packs as kp

    monkeypatch.setattr(kp, "COMMUNITY_KEY_MAPS", {"k-gate": "woods"})
    maps = [
        {
            "name": "海关",
            "normalizedName": "customs",
            "locks": [{"key": _key("k-gate", "大门钥匙")}],
        }
    ]
    catalog = [
        {
            "id": "k-gate",
            "name": "大门钥匙",
            "types": ["keys"],
            "handbook_ids": [KEYS_ROOT],
        }
    ]
    out = group_key_packs(maps, catalog)
    by_slug = {row["slug"]: row for row in out["maps"]}
    assert "woods" not in by_slug
    gate = by_slug["customs"]["keys"][0]
    assert gate["id"] == "k-gate"
    assert gate["community"] is False
    assert gate["lock_count"] == 1


def test_group_skips_hub_maps() -> None:
    maps = [
        {
            "name": "开放世界",
            "normalizedName": "openworld",
            "locks": [{"key": _key("k1", "钥")}],
        },
        {
            "name": "海关",
            "normalizedName": "customs",
            "locks": [{"key": _key("k2", "海关钥")}],
        },
    ]
    out = group_key_packs(maps, [])
    assert [row["slug"] for row in out["maps"]] == ["customs"]


def test_build_key_source_index_joins_barter_craft_task_flea() -> None:
    index = build_key_source_index(
        barters=[
            {
                "trader_id": "54cb57776803fa99248b456e",
                "trader_slug": "therapist",
                "trader_name": "Therapist",
                "min_trader_level": 2,
                "offered_item": {"id": "dorm-114"},
            },
            {
                "trader_id": "54cb57776803fa99248b456e",
                "trader_slug": "therapist",
                "trader_name": "Therapist",
                "min_trader_level": 1,
                "offered_item": {"id": "dorm-114"},
            },
        ],
        crafts=[
            {
                "station_slug": "intelligence-center",
                "station_name": "情报中心",
                "level": 2,
                "product_item": {"id": "dorm-114"},
            }
        ],
        task_rows=[
            {
                "id": "task-1",
                "name": "验收",
                "finish_rewards": {"items": [{"id": "dorm-114"}]},
            },
            {
                "id": "task-2",
                "name": "raw 任务",
                "finishRewards": {"items": [{"item": "quest-only", "count": 1}]},
            },
        ],
        catalog_rows=[
            {
                "id": "dorm-114",
                "types": ["keys"],
                "last_low_price": 88000,
            },
            {"id": "quest-only", "types": ["keys", "noFlea"]},
        ],
    )
    dorm = index["dorm-114"]
    assert dorm["barters"] == [
        {"trader_slug": "therapist", "trader_name": "Therapist", "min_trader_level": 1}
    ]
    assert dorm["crafts"][0]["station_name"] == "情报中心"
    assert [row["id"] for row in dorm["tasks"]] == ["task-1"]
    assert dorm["flea"] == {"price": 88000}
    assert index["quest-only"]["tasks"][0]["id"] == "task-2"
    assert index["quest-only"]["flea"] is None


def test_task_source_replaces_placeholder_name() -> None:
    index = build_key_source_index(
        task_rows=[
            {
                "id": "6745fcde0dfbbc74ca0f721d",
                "name": "6745fcde0dfbbc74ca0f721d name",
                "normalizedName": "old-house-toilet",
                "finishRewards": {
                    "items": [{"item": "old-toilet-key", "count": 1}]
                },
            }
        ]
    )
    assert index["old-toilet-key"]["tasks"] == [
        {"id": "6745fcde0dfbbc74ca0f721d", "name": "Old House Toilet"}
    ]


def test_group_collects_lock_types_and_power() -> None:
    maps = [
        {
            "name": "海关",
            "normalizedName": "customs",
            "locks": [
                {
                    "lockType": "door",
                    "needsPower": False,
                    "key": _key("dorm-114", "宿舍 114"),
                },
                {
                    "lockType": "door",
                    "key": _key("dorm-114", "宿舍 114"),
                },
                {
                    "lockType": "container",
                    "needsPower": True,
                    "key": _key("dorm-114", "宿舍 114"),
                },
            ],
        }
    ]
    catalog = [
        {
            "id": "dorm-114",
            "name": "宿舍 114 钥匙",
            "types": ["keys"],
            "handbook_ids": [KEYS_ROOT],
            "description": "三层宿舍 114 房间的钥匙。",
        }
    ]
    out = group_key_packs(maps, catalog)
    key = out["maps"][0]["keys"][0]
    assert key["lock_count"] == 3
    assert key["lock_types"] == ["door", "container"]
    assert key["needs_power"] is True
    assert key["description"] == "三层宿舍 114 房间的钥匙。"


def test_build_key_usage_index_joins_needed_keys_and_objectives() -> None:
    index = build_key_usage_index(
        [
            {
                "id": "task-1",
                "name": "验收",
                "neededKeys": [{"keys": [{"id": "dorm-114"}]}],
                "objectives": [
                    {
                        "id": "obj-1",
                        "description": "打开宿舍 114 的门",
                        "requiredKeys": [[{"id": "dorm-114"}]],
                    }
                ],
            },
            {
                "id": "task-2",
                "name": "缺货",
                "needed_keys": [{"keys": [{"id": "dorm-114"}, {"id": "other"}]}],
            },
        ]
    )
    dorm = {row["id"]: row for row in index["dorm-114"]}
    assert set(dorm) == {"task-1", "task-2"}
    assert dorm["task-1"]["notes"] == ["打开宿舍 114 的门"]
    assert dorm["task-2"]["notes"] == []
    assert [row["id"] for row in index["other"]] == ["task-2"]


def test_attach_key_usage_fills_grouped_keys() -> None:
    grouped = {
        "maps": [{"slug": "customs", "keys": [{"id": "dorm-114", "name": "114"}]}],
        "unbound": [{"id": "lonely", "name": "无用途"}],
    }
    attach_key_usage(
        grouped,
        {
            "dorm-114": [
                {"id": "t", "name": "验收", "notes": ["打开宿舍 114 的门"]}
            ]
        },
    )
    assert grouped["maps"][0]["keys"][0]["used_in_tasks"][0]["name"] == "验收"
    assert grouped["unbound"][0]["used_in_tasks"] == []


def test_attach_key_sources_fills_grouped_keys() -> None:
    grouped = {
        "maps": [{"slug": "customs", "keys": [{"id": "dorm-114", "name": "114"}]}],
        "unbound": [{"id": "lonely", "name": "无来源"}],
    }
    attach_key_sources(
        grouped,
        {
            "dorm-114": {
                "barters": [],
                "crafts": [],
                "tasks": [{"id": "t", "name": "任务"}],
                "flea": {"price": 1},
            }
        },
    )
    assert grouped["maps"][0]["keys"][0]["sources"]["tasks"][0]["id"] == "t"
    assert grouped["unbound"][0]["sources"]["flea"] is None


def test_parse_json_maps_locks_from_id_dict() -> None:
    rows = parse_json_maps_locks(
        {
            "data": {
                "maps": {
                    "56f40101d2720b2a4d8b45d6": {
                        "name": "Customs",
                        "normalizedName": "customs",
                        "locks": [{"key": "dorm-114"}],
                        "accessKeys": [],
                    },
                    "5b0fc42d86f7744a585f9105": {
                        "name": "The Lab",
                        "normalizedName": "the-lab",
                        "locks": [],
                        "accessKeys": ["lab-card"],
                    },
                    "skip": "not-a-map",
                }
            }
        }
    )
    by_slug = {row["normalizedName"]: row for row in rows}
    assert by_slug["customs"]["name"] == "海关"
    assert by_slug["customs"]["locks"][0]["key"] == "dorm-114"
    assert by_slug["the-lab"]["accessKeys"] == ["lab-card"]


def test_parse_json_maps_locks_rejects_empty() -> None:
    with pytest.raises(TarkovKeyPacksError, match="无效"):
        parse_json_maps_locks({"data": {"maps": None}})
    with pytest.raises(TarkovKeyPacksError, match="未解析"):
        parse_json_maps_locks({"data": {"maps": {}}})


def test_parse_json_maps_locks_rejects_boss_slim_without_locks() -> None:
    payload = {
        "maps": {
            "1": {
                "normalizedName": "customs",
                "bosses": [{"mob": "reshala"}],
                "extracts": [],
            }
        }
    }
    assert maps_have_lock_data(
        [{"normalizedName": "customs", "locks": [], "accessKeys": []}]
    ) is False
    with pytest.raises(TarkovKeyPacksError, match="没有门锁"):
        parse_json_maps_locks(payload)


def test_group_accepts_json_string_key_ids() -> None:
    maps = parse_json_maps_locks(
        {
            "data": {
                "maps": {
                    "1": {
                        "normalizedName": "customs",
                        "locks": [{"key": "dorm-114"}],
                        "accessKeys": [],
                    }
                }
            }
        }
    )
    out = group_key_packs(maps, [])
    assert out["maps"][0]["keys"][0]["id"] == "dorm-114"
    assert out["maps"][0]["keys"][0]["lock_count"] == 1


def test_fetch_json_maps_locks(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tarkov import key_packs as kp

    kp._lock_cache.clear()

    def fake_http(_url: str, **_kwargs):
        return (
            b'{"data":{"maps":{"1":{"name":"Customs","normalizedName":"customs",'
            b'"locks":[{"key":"dorm-114"}],"accessKeys":[]}}}}'
        )

    monkeypatch.setattr(kp, "_http_request", fake_http)
    maps, source = fetch_map_locks()
    assert source == SOURCE_JSON
    assert maps[0]["normalizedName"] == "customs"
    assert maps[0]["locks"][0]["key"] == "dorm-114"


def test_fetch_uses_stale_cache_when_json_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tarkov import key_packs as kp

    kp._lock_cache.clear()
    kp._lock_cache[kp._cache_key("pvp")] = {
        "at": 0.0,
        "maps": [{"normalizedName": "woods", "locks": [], "accessKeys": []}],
        "source": SOURCE_JSON,
    }

    def fake_http(_url: str, **_kwargs):
        raise TarkovKeyPacksError("下载失败 HTTP 422: boom")

    monkeypatch.setattr(kp, "_http_request", fake_http)
    maps, source = fetch_map_locks()
    assert source == SOURCE_STALE
    assert maps[0]["normalizedName"] == "woods"


def test_fetch_fail_without_cache_is_friendly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.tarkov import key_packs as kp

    kp._lock_cache.clear()

    def fake_http(_url: str, **_kwargs):
        raise TarkovKeyPacksError("下载失败 HTTP 422: boom")

    monkeypatch.setattr(kp, "_http_request", fake_http)
    with pytest.raises(TarkovKeyPacksError, match="暂时拉不到") as exc:
        fetch_map_locks()
    assert "422" not in str(exc.value)
    assert str(exc.value) == UNAVAILABLE_MSG


def test_fetch_ignores_persisted_slim_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tarkov import key_packs as kp
    from app.services.tarkov import upstream as upstream_svc

    kp._lock_cache.clear()

    monkeypatch.setattr(
        upstream_svc,
        "load_raw",
        lambda *_a, **_k: {
            "maps": {
                "1": {
                    "normalizedName": "customs",
                    "bosses": [{"mob": "reshala"}],
                    "extracts": [],
                }
            }
        },
    )

    def fake_http(_url: str, **_kwargs):
        return (
            b'{"data":{"maps":{"1":{"normalizedName":"customs",'
            b'"locks":[{"key":"dorm-114"}],"accessKeys":[]}}}}'
        )

    monkeypatch.setattr(kp, "_http_request", fake_http)
    maps, source = fetch_map_locks(db=object())
    assert source == SOURCE_JSON
    assert maps[0]["locks"][0]["key"] == "dorm-114"
