"""Task line index: mutex failure vs ancestor-fork unreachable."""

from __future__ import annotations

from app.services.tarkov.task_lines import index_task_lines

BTR = {
    "id": "656f0f98d80a697f855d34b1",
    "normalizedName": "btr-driver",
}


def _task(
    ident: str,
    name: str,
    *,
    prereqs: list[str] | None = None,
    fail: list[str] | None = None,
    faction: str = "Any",
    prestige: int = 0,
    trader: dict | str | None = None,
) -> dict:
    raw: dict = {
        "id": ident,
        "name": name,
        "normalizedName": ident,
        "factionName": faction,
        "trader": BTR if trader is None else trader,
        "taskRequirements": [
            {"task": item, "status": ["complete"]} for item in (prereqs or [])
        ],
        "failConditions": [
            {"type": "taskStatus", "task": item, "status": ["complete"]}
            for item in (fail or [])
        ],
    }
    if prestige:
        raw["requiredPrestige"] = {"prestigeLevel": prestige}
    return raw


def _btr_map() -> dict[str, dict]:
    return {
        "stick": _task("stick", "横插一杠"),
        "business": _task("business", "稳定业务"),
        "bat1": _task("bat1", "电池换新", prereqs=["stick"], fail=["bat2"]),
        "bat2": _task("bat2", "电池换新", prereqs=["business"]),
        "disco": _task("disco", "反将一军"),
        "price1": _task("price1", "独立的代价", prereqs=["bat1", "disco"], fail=["choose"]),
        "price2": _task("price2", "独立的代价", prereqs=["bat2", "disco"], fail=["choose"]),
        "choose": _task("choose", "识时务者为俊杰", fail=["price1"]),
    }


def test_btr_mutex_symmetrized_and_price_blocked_by_other_battery():
    index = index_task_lines(_btr_map(), {})
    assert index["bat1"]["mutex_ids"] == ["bat2"]
    assert index["bat2"]["mutex_ids"] == ["bat1"]
    assert index["bat1"]["blocked_by"] == []
    assert index["bat2"]["blocked_by"] == []
    assert index["price1"]["mutex_ids"] == ["choose"]
    assert index["price2"]["mutex_ids"] == ["choose"]
    assert index["choose"]["mutex_ids"] == ["price1", "price2"]
    assert index["price1"]["blocked_by"] == ["bat2"]
    assert index["price2"]["blocked_by"] == ["bat1"]
    assert index["stick"]["mutex_ids"] == []
    assert index["stick"]["blocked_by"] == []
    assert "stick" not in index["price2"]["blocked_by"]
    assert "business" not in index["price1"]["blocked_by"]
    assert index["price1"]["prereq_ids"] == ["bat1", "disco"]
    assert index["price2"]["prereq_ids"] == ["bat2", "disco"]
    assert index["stick"]["prereq_ids"] == []


def test_prereq_ids_ignore_active_only_requirements():
    payload = {
        "start": _task("start", "开始"),
        "later": {
            **_task("later", "后续", prereqs=["start"]),
            "taskRequirements": [
                {"task": "start", "status": ["active"]},
            ],
        },
        "done": _task("done", "完成后续", prereqs=["start"]),
    }
    index = index_task_lines(payload, {})
    assert index["later"]["prereq_ids"] == []
    assert index["done"]["prereq_ids"] == ["start"]


def test_btr_line_hint_skips_same_name_mutex_pair():
    index = index_task_lines(_btr_map(), {})
    assert index["price1"]["line_hint"] == "经「横插一杠」"
    assert index["price2"]["line_hint"] == "经「稳定业务」"
    assert index["bat1"]["line_hint"] == "经「横插一杠」"
    assert index["bat2"]["line_hint"] == "经「稳定业务」"
    assert index["disco"]["line_hint"] == ""
    assert index["choose"]["line_hint"] == ""


def test_three_way_mutex_has_no_line_hint():
    payload = {
        "chem": _task("chem", "化学-第4部分", fail=["curio", "big"]),
        "curio": _task("curio", "好奇心", fail=["chem", "big"]),
        "big": _task("big", "大客户", fail=["chem", "curio"]),
        "plain": _task("plain", "首秀"),
    }
    index = index_task_lines(payload, {})
    assert set(index["chem"]["mutex_ids"]) == {"curio", "big"}
    assert set(index["curio"]["mutex_ids"]) == {"chem", "big"}
    assert set(index["big"]["mutex_ids"]) == {"chem", "curio"}
    assert index["chem"]["blocked_by"] == []
    assert index["chem"]["line_hint"] == ""
    assert index["plain"]["mutex_ids"] == []
    assert index["plain"]["blocked_by"] == []
    assert index["plain"]["line_hint"] == ""


def test_faction_and_prestige_hints():
    usec = {"id": "prapor", "normalizedName": "prapor"}
    payload = {
        "u": _task("u", "湿活", faction="USEC", trader=usec),
        "b": _task("b", "湿活", faction="BEAR", trader=usec),
        "nb": _task("nb", "新的开始", trader=usec),
        "nb5": _task("nb5", "新的开始", prestige=5, trader=usec),
    }
    index = index_task_lines(payload, {})
    assert index["u"]["line_hint"] == "USEC"
    assert index["b"]["line_hint"] == "BEAR"
    assert index["nb"]["line_hint"] == ""
    assert index["nb5"]["line_hint"] == "声望 5"


def test_locale_names_drive_cluster_and_hint():
    payload = {
        "stick": _task("stick", "stick"),
        "business": _task("business", "business"),
        "bat1": _task("bat1", "battery", prereqs=["stick"], fail=["bat2"]),
        "bat2": _task("bat2", "battery", prereqs=["business"]),
        "p1": _task("p1", "price", prereqs=["bat1"]),
        "p2": _task("p2", "price", prereqs=["bat2"]),
    }
    locale = {
        "stick name": "横插一杠",
        "business name": "稳定业务",
        "bat1 name": "电池换新",
        "bat2 name": "电池换新",
        "p1 name": "独立的代价",
        "p2 name": "独立的代价",
    }
    index = index_task_lines(payload, locale)
    assert index["p1"]["line_hint"] == "经「横插一杠」"
    assert index["p2"]["line_hint"] == "经「稳定业务」"
    assert index["p2"]["blocked_by"] == ["bat1"]
