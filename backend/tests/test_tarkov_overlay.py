"""tarkov-data-overlay 内存合入：不写进 json.tarkov.dev raw。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.user import User, UserRole
from app.services.tarkov import overlay as overlay_svc
from app.services.tarkov import task_dones as dones
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import upstream as upstream_svc
from app.services.tarkov.game_mode import game_mode_scope
from app.services.tarkov.guides import parse_crafts
from app.services.tarkov.overlay import apply_overlay
from app.services.tarkov.tasks import parse_task_rows

PRAPOR = "54cb50c76803fa8b248b4571"


def _task(tid: str, **fields: object) -> dict:
    row = {
        "id": tid,
        "name": tid,
        "objectives": [
            {"id": "o1", "type": "visit", "description": "go", "count": 1},
        ],
        "traderRequirements": [
            {
                "id": "req-1",
                "trader": {"id": PRAPOR, "name": "Prapor"},
                "requirementType": "level",
                "compareMethod": ">=",
                "value": 1,
            }
        ],
        "experience": 100,
    }
    row.update(fields)
    return row


def test_apply_overlay_none_is_identity() -> None:
    payload = {"tasks": {"t1": _task("t1")}}
    assert apply_overlay("tasks", payload, None) is payload


def test_apply_overlay_unknown_resource_is_identity() -> None:
    payload = {"maps": {"m1": {"id": "m1"}}}
    overlay = {"tasks": {"t1": {"disabled": True}}}
    assert apply_overlay("maps", payload, overlay) is payload


def test_task_shallow_fields_and_objective_id_patch() -> None:
    payload = {"data": {"tasks": {"t1": _task("t1")}}}
    overlay = {
        "tasks": {
            "t1": {
                "experience": 999,
                "minPlayerLevel": 10,
                "objectives": {"o1": {"count": 5, "description": "patched"}},
                "objectivesAdd": [{"id": "o2", "type": "extract", "description": "leave"}],
            }
        }
    }
    out = apply_overlay("tasks", payload, overlay)
    task = out["data"]["tasks"]["t1"]
    assert task["experience"] == 999
    assert task["minPlayerLevel"] == 10
    assert task["objectives"][0]["count"] == 5
    assert task["objectives"][0]["description"] == "patched"
    assert task["objectives"][0]["type"] == "visit"
    assert task["objectives"][1]["id"] == "o2"


def test_trader_requirements_patch_by_id_empty_clears_absent_keeps() -> None:
    payload = {"tasks": {"t1": _task("t1"), "t2": _task("t2"), "t3": _task("t3")}}
    overlay = {
        "tasks": {
            "t1": {
                "traderRequirements": [
                    {
                        "id": "req-1",
                        "value": 4,
                    },
                    {
                        "id": "overlay.t1.fence.rep",
                        "requirementType": "reputation",
                        "compareMethod": ">=",
                        "value": 0,
                        "trader": {"id": "579dc571d53a0658a154fbec", "name": "Fence"},
                    },
                ]
            },
            "t2": {"traderRequirements": []},
        }
    }
    out = apply_overlay("tasks", payload, overlay)
    t1 = out["tasks"]["t1"]["traderRequirements"]
    assert t1[0]["id"] == "req-1"
    assert t1[0]["value"] == 4
    assert t1[0]["requirementType"] == "level"
    assert t1[1]["id"] == "overlay.t1.fence.rep"
    assert out["tasks"]["t2"]["traderRequirements"] == []
    assert out["tasks"]["t3"]["traderRequirements"][0]["value"] == 1


def test_disabled_tasks_removed_and_tasks_add() -> None:
    payload = {"tasks": {"keep": _task("keep"), "gone": _task("gone")}}
    overlay = {
        "tasks": {"gone": {"disabled": True}},
        "tasksAdd": {
            "new_beginning_prestige_5": {
                "id": "new_beginning_prestige_5",
                "name": "New Beginning",
                "objectives": [],
            }
        },
    }
    out = apply_overlay("tasks", payload, overlay)
    assert "gone" not in out["tasks"]
    assert "keep" in out["tasks"]
    assert out["tasks"]["new_beginning_prestige_5"]["name"] == "New Beginning"
    rows = parse_task_rows(out)
    ids = {row["id"] for row in rows}
    assert ids == {"keep", "new_beginning_prestige_5"}


def test_pve_mode_overrides_shared_and_does_not_use_locales() -> None:
    payload = {
        "tasks": {"t1": _task("t1")},
        "locale": {"t1 name": "中文名"},
    }
    overlay = {
        "tasks": {"t1": {"experience": 10}},
        "modes": {
            "regular": {"tasks": {"t1": {"experience": 20}}},
            "pve": {"tasks": {"t1": {"experience": 30, "objectives": {"o1": {"count": 36}}}}},
        },
        "locales": {"en": {"tasks": {"t1": {"name": "English"}}}},
    }
    with game_mode_scope("pvp"):
        pvp = apply_overlay("tasks", {"tasks": {"t1": _task("t1")}}, overlay)
    with game_mode_scope("pve"):
        pve = apply_overlay("tasks", payload, overlay)
    assert pvp["tasks"]["t1"]["experience"] == 20
    assert pve["tasks"]["t1"]["experience"] == 30
    assert pve["tasks"]["t1"]["objectives"][0]["count"] == 36
    assert pve["locale"]["t1 name"] == "中文名"
    assert pve["tasks"]["t1"]["name"] == "t1"


def test_items_add_skips_existing() -> None:
    payload = {"data": {"items": {"a1": {"id": "a1", "name": "A"}}}}
    overlay = {
        "itemsAdd": {
            "a1": {"id": "a1", "name": "Should not win"},
            "evt": {"id": "evt", "name": "Event Item", "shortName": "EVT"},
        }
    }
    out = apply_overlay("items", payload, overlay)
    items = out["data"]["items"]
    assert items["a1"]["name"] == "A"
    assert items["evt"]["shortName"] == "EVT"


def test_crafts_add_appends_missing_and_parse_sees_it() -> None:
    payload = {
        "hideout": {
            "st1": {"id": "st1", "normalizedName": "workbench", "name": "Workbench", "levels": []}
        },
        "barters": [],
        "crafts": [
            {
                "id": "c1",
                "station": "st1",
                "level": 1,
                "duration": 10,
                "requiredItems": [{"item": "i1", "count": 1, "attributes": {}}],
                "productItem": {"item": "i2", "count": 1, "attributes": {}},
            }
        ],
        "locale": {},
    }
    overlay = {
        "craftsAdd": {
            "c1": {"id": "c1", "station": "st1", "productItem": {"item": "x", "count": 1}},
            "c2": {
                "id": "c2",
                "station": "st1",
                "level": 2,
                "duration": 60,
                "requiredItems": [{"item": "i3", "count": 2, "attributes": {}}],
                "productItem": {"item": "i4", "count": 1, "attributes": {}},
            },
        }
    }
    out = apply_overlay("crafts", payload, overlay)
    ids = [row["id"] for row in out["crafts"]]
    assert ids.count("c1") == 1
    assert "c2" in ids
    parsed = parse_crafts(out)
    assert {row["id"] for row in parsed} == {"c1", "c2"}


def test_disabled_overlay_task_hidden_from_progress_not_deleted() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    user = User(
        username="a",
        display_name="甲",
        password_hash="x",
        role=UserRole.user,
    )
    db.add(user)
    db.flush()
    tasks_svc._parsed_cache = None
    tasks_svc._raid_prep_cache.clear()
    tasks_svc._raid_prep_index_cache.clear()
    with game_mode_scope("pvp"):
        upstream_svc.persist_raw(
            db,
            "tasks",
            {
                "tasks": {
                    "keep": _task("keep"),
                    "gone": _task("gone"),
                    "live": _task("live"),
                }
            },
            source="test",
            note="fixture",
            commit=False,
        )
        overlay_svc.persist_overlay(
            db,
            {"tasks": {"gone": {"disabled": True}}},
        )
        dones.write_progress(
            db,
            user,
            ["keep", "gone"],
            ["live", "gone"],
            replace=True,
        )
        catalog = tasks_svc.catalog_task_id_set(db)
        stored_done, stored_started = dones.list_progress(db, user.id)
        shown_done, shown_started = dones.filter_visible_progress(
            stored_done,
            stored_started,
            catalog,
        )
    assert catalog == {"keep", "live"}
    assert stored_done == ["gone", "keep"]
    assert stored_started == ["live"]
    assert shown_done == ["keep"]
    assert shown_started == ["live"]
    assert dones.list_task_ids(db, user.id) == ["gone", "keep"]
