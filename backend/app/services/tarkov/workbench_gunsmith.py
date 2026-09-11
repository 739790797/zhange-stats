"""枪匠任务：从 tasks dump 的 buildWeapon 投影约束，在工作台索引上对照 / 求解。

不 vendor EFTForge 的手抄 JSON。类别组保留 dump 嵌套（内层 OR、组间 AND）。
求解是约束满足 + 局部替换，不是 HiGHS；装不上的转接座会判不可行。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import workbench as wb

_ATTR_KEYS = {
    "ergonomics": "ergonomics",
    "recoil": "recoil_sum",
    "recoilsum": "recoil_sum",
    "recoil_sum": "recoil_sum",
    "magazinecapacity": "mag_capacity",
    "magazine_capacity": "mag_capacity",
    "magsize": "mag_capacity",
    "sightingrange": "sighting_range",
    "effectivedistance": "sighting_range",
    "weight": "weight",
    "durability": "durability",
    "width": "width",
    "height": "height",
}

# 耐久在上交时检查；格仓要折叠，工作台暂不对照 ExtraSize。

_MIN_CMP = {">=", ">", "=>"}
_MAX_CMP = {"<=", "<", "=<"}

_CANDIDATES_PER_SLOT = 24
_SEARCH_ITERS = 80


def _named_id(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("id") or "").strip()


def _named_pack(row: dict[str, Any] | None) -> dict[str, str]:
    ident = _named_id(row)
    name = str((row or {}).get("name") or "").strip()
    return {"id": ident, "name": name or ident}


def _constraint_field(name: str) -> str:
    key = "".join(ch for ch in (name or "").strip().lower() if ch.isalnum() or ch == "_")
    return _ATTR_KEYS.get(key, "")


def constraints_from_attributes(attrs: list[dict[str, Any]] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in attrs or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        field = _constraint_field(name)
        if not field:
            continue
        raw = row.get("value")
        if raw is None or raw == "":
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        method = str(row.get("compare_method") or "").strip()
        if tasks_svc._attribute_is_unconstrained(name, method, value):
            continue
        if method in _MIN_CMP or (not method and field == "ergonomics"):
            out[f"min_{field}"] = value
        elif method in _MAX_CMP or (not method and field in {"recoil_sum", "weight"}):
            out[f"max_{field}"] = value
        elif method in _MIN_CMP:
            out[f"min_{field}"] = value
        elif method in _MAX_CMP:
            out[f"max_{field}"] = value
    return out


def _raw_objective_map(raw_task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for index, obj in enumerate(raw_task.get("objectives") or []):
        if not isinstance(obj, dict):
            continue
        ident = str(obj.get("id") or "").strip() or f"i:{index}"
        out[ident] = obj
    return out


def collect_gunsmith_tasks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从 tasks dump 抽出 buildWeapon；一条目标一行。"""
    locale = tasks_svc._locale_map(payload)
    quest_items = tasks_svc._quest_items_map(payload)
    tasks = tasks_svc._tasks_map(payload)
    out: list[dict[str, Any]] = []
    for raw in tasks.values():
        if not isinstance(raw, dict):
            continue
        detail = tasks_svc.project_task_detail(
            raw,
            locale,
            quest_items=quest_items,
            tasks_by_id=tasks,
            include_unlocks=False,
        )
        if detail is None:
            continue
        raw_objs = _raw_objective_map(raw)
        for obj in detail.get("objectives") or []:
            if not isinstance(obj, dict) or str(obj.get("type") or "") != "buildWeapon":
                continue
            obj_id = str(obj.get("id") or "").strip()
            items = [row for row in (obj.get("items") or []) if isinstance(row, dict)]
            weapon = items[0] if items else None
            weapon_id = _named_id(weapon)
            if not weapon_id:
                continue
            raw_obj = raw_objs.get(obj_id) or {}
            cat_groups = tasks_svc._named_ref_groups(
                raw_obj.get("containsCategory"),
                locale,
                kind="category",
            )
            if not cat_groups:
                cats = [
                    _named_pack(row)
                    for row in (obj.get("contains_category") or [])
                    if _named_id(row)
                ]
                cat_groups = [[row] for row in cats]
            required = [
                _named_pack(row)
                for row in (obj.get("contains_all") or [])
                if _named_id(row)
            ]
            out.append(
                {
                    "id": f"{detail['id']}:{obj_id}" if obj_id else str(detail["id"]),
                    "task_id": str(detail.get("id") or ""),
                    "objective_id": obj_id,
                    "task_name": str(detail.get("name") or ""),
                    "trader_slug": str(detail.get("trader_slug") or ""),
                    "trader_name": str(detail.get("trader_name") or ""),
                    "faction_name": str(detail.get("faction_name") or "Any"),
                    "weapon_id": weapon_id,
                    "weapon_name": str((weapon or {}).get("name") or weapon_id),
                    "weapon_image": str((weapon or {}).get("icon_link") or ""),
                    "constraints": constraints_from_attributes(obj.get("attributes")),
                    "required_items": required,
                    "required_category_groups": [
                        [_named_pack(row) for row in group if _named_id(row)]
                        for group in cat_groups
                        if group
                    ],
                }
            )
    out.sort(key=lambda row: (row["task_name"], row["objective_id"]))
    return out


def _placeholder(ident: str, name: str) -> bool:
    return tasks_svc._is_placeholder_name(ident, name)


def _apply_display_name(ref: dict[str, Any], names: dict[str, str]) -> None:
    ident = str(ref.get("id") or "").strip()
    if not ident:
        return
    name = str(ref.get("name") or "").strip()
    if name and not _placeholder(ident, name):
        return
    hit = names.get(ident)
    if hit:
        ref["name"] = hit


def _wanted_placeholder_ids(rows: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    items: set[str] = set()
    cats: set[str] = set()
    for row in rows:
        for item in row.get("required_items") or []:
            ident = str((item or {}).get("id") or "").strip()
            if ident and _placeholder(ident, str((item or {}).get("name") or "")):
                items.add(ident)
        for group in row.get("required_category_groups") or []:
            for cat in group or []:
                ident = str((cat or {}).get("id") or "").strip()
                if ident and _placeholder(ident, str((cat or {}).get("name") or "")):
                    cats.add(ident)
    return items, cats


def _names_from_index(index: wb.WorkbenchIndex | None, wanted: set[str]) -> dict[str, str]:
    if index is None:
        return {}
    out: dict[str, str] = {}
    for ident in wanted:
        item = index.items.get(ident)
        if item is None:
            continue
        name = str(item.name or item.short_name or "").strip()
        if name and not _placeholder(ident, name):
            out[ident] = name
    return out


def _names_from_items_dump(
    db: Session, wanted_items: set[str], wanted_cats: set[str]
) -> tuple[dict[str, str], dict[str, str]]:
    if not wanted_items and not wanted_cats:
        return {}, {}
    try:
        from app.services.tarkov import catalog as catalog_svc
        from app.services.tarkov import upstream as upstream_svc
        from app.services.tarkov.catalog import _row_from_raw, iter_raw_items
        from app.services.tarkov.items import _locale_map as items_locale
    except Exception:  # noqa: BLE001
        return {}, {}
    try:
        source, payload, _synced, _note = upstream_svc.load_main_payload(db, "items")
    except Exception:  # noqa: BLE001
        return {}, {}
    item_names: dict[str, str] = {}
    if wanted_items:
        locale = items_locale(payload)
        try:
            for ident, raw in iter_raw_items(source, payload):
                if ident not in wanted_items or ident in item_names:
                    continue
                hit = _row_from_raw(ident, raw, locale)
                name = str((hit or {}).get("name") or "").strip()
                if name and not _placeholder(ident, name):
                    item_names[ident] = name
                if len(item_names) >= len(wanted_items):
                    break
        except Exception:  # noqa: BLE001
            item_names = {}
    try:
        cat_names = catalog_svc.lookup_category_names(payload, wanted_cats)
    except Exception:  # noqa: BLE001
        cat_names = {}
    return item_names, cat_names


def _fill_gunsmith_display_names(
    db: Session | None,
    rows: list[dict[str, Any]],
    index: wb.WorkbenchIndex | None,
) -> None:
    wanted_items, wanted_cats = _wanted_placeholder_ids(rows)
    item_names = _names_from_index(index, wanted_items)
    still_items = wanted_items - set(item_names)
    dump_items, cat_names = (
        _names_from_items_dump(db, still_items, wanted_cats) if db is not None else ({}, {})
    )
    item_names.update(dump_items)
    for ident, name in cat_names.items():
        item_names.setdefault(ident, name)
    for ident, name in item_names.items():
        cat_names.setdefault(ident, name)
    for row in rows:
        for item in row.get("required_items") or []:
            _apply_display_name(item, item_names)
            _apply_display_name(item, cat_names)
        for group in row.get("required_category_groups") or []:
            for cat in group or []:
                _apply_display_name(cat, cat_names)
                _apply_display_name(cat, item_names)


def list_gunsmith_tasks(db: Session) -> dict[str, Any]:
    tasks_svc.ensure_tasks(db)
    source, payload, synced_at, note = tasks_svc._load_payload(db)
    rows = collect_gunsmith_tasks(payload)
    try:
        index = wb.load_index(db)
    except wb.TarkovWorkbenchError:
        index = None
    packed: list[dict[str, Any]] = []
    for row in rows:
        weapon_id = row["weapon_id"]
        loadable = False
        if index is not None:
            try:
                gun = wb._require_gun(index, weapon_id)
                loadable = True
                row = {
                    **row,
                    "weapon_id": gun.id,
                    "weapon_name": gun.name or row["weapon_name"],
                    "weapon_image": gun.preset_image_link or gun.image_link or row["weapon_image"],
                }
            except wb.TarkovWorkbenchError:
                loadable = False
        packed.append({**row, "loadable": loadable})
    _fill_gunsmith_display_names(db, packed, index)
    return {
        "items": packed,
        "task_count": len(packed),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def get_gunsmith_task(
    db: Session,
    task_id: str,
    objective_id: str | None = None,
) -> dict[str, Any]:
    tid = (task_id or "").strip()
    oid = (objective_id or "").strip()
    if not tid:
        raise wb.TarkovWorkbenchError("任务 id 无效", status_code=400)
    bundled = list_gunsmith_tasks(db)
    rows = [
        row
        for row in bundled["items"]
        if row["task_id"] == tid and (not oid or row["objective_id"] == oid)
    ]
    if not rows:
        raise wb.TarkovWorkbenchError("未找到枪匠任务", status_code=404)
    return rows[0]


def _pairs_list(installed: dict[str, str]) -> list[tuple[str, str]]:
    return [(slot_id, item_id) for slot_id, item_id in installed.items() if item_id]


def _reachable_slots(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    installed: dict[str, str],
) -> list[wb.WbSlot]:
    out: list[wb.WbSlot] = []

    def walk(item_id: str) -> None:
        item = index.items.get(item_id)
        if not item:
            return
        for slot in item.slots:
            out.append(slot)
            child = installed.get(slot.id, "")
            if child:
                walk(child)

    walk(gun.id)
    return out


def _prune_slot(index: wb.WorkbenchIndex, installed: dict[str, str], slot_id: str) -> None:
    old = installed.pop(slot_id, None)
    if not old:
        return
    item = index.items.get(old)
    if not item:
        return
    for slot in item.slots:
        _prune_slot(index, installed, slot.id)


def _slot_of_item(installed: dict[str, str], item_id: str) -> str:
    for slot_id, installed_id in installed.items():
        if installed_id == item_id:
            return slot_id
    return ""


def _set_item(
    index: wb.WorkbenchIndex,
    installed: dict[str, str],
    slot_id: str,
    item_id: str | None,
) -> dict[str, str]:
    nxt = dict(installed)
    _prune_slot(index, nxt, slot_id)
    if not item_id:
        return nxt
    item = index.items.get(item_id)
    if item:
        for other_id in list(item.conflicting):
            sid = _slot_of_item(nxt, other_id)
            if sid:
                _prune_slot(index, nxt, sid)
        for sid, iid in list(nxt.items()):
            other = index.items.get(iid)
            if other and item_id in other.conflicting:
                _prune_slot(index, nxt, sid)
    nxt[slot_id] = item_id
    return nxt


def _installed_ids(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    installed: dict[str, str],
) -> list[str]:
    return wb._collect_installed_ids(index, gun.id, installed)


def _item_matches_group(item: wb.WbItem | None, group_ids: set[str]) -> bool:
    if not item or not group_ids:
        return False
    return bool(item.categories & group_ids)


def evaluate_build(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    installed: dict[str, str],
    spec: dict[str, Any],
    ammo_id: str | None = None,
) -> dict[str, Any]:
    pairs = _pairs_list(installed)
    stats = wb.calculate_stats(index, gun.id, pairs, ammo_id)
    installed_ids = set(_installed_ids(index, gun, installed))
    items = [index.items.get(iid) for iid in installed_ids]
    missing_items: list[dict[str, str]] = []
    for row in spec.get("required_items") or []:
        ident = _named_id(row)
        if ident and ident not in installed_ids:
            missing_items.append(_named_pack(row))
    missing_categories: list[list[dict[str, str]]] = []
    for group in spec.get("required_category_groups") or []:
        ids = {_named_id(row) for row in group if _named_id(row)}
        if not ids:
            continue
        if not any(_item_matches_group(item, ids) for item in items if item):
            missing_categories.append([_named_pack(row) for row in group if _named_id(row)])
    constraints = spec.get("constraints") or {}
    ergo = float(stats.get("ergonomics") or 0)
    recoil_sum = int(stats.get("recoil_vertical") or 0) + int(
        stats.get("recoil_horizontal") or 0
    )
    weight = float(stats.get("weight") or 0)
    mag = int(stats.get("mag_capacity") or 0)
    sight = int(stats.get("sighting_range") or 0)
    unmet: list[str] = []

    def _gap(key: str, actual: float, want_min: bool) -> None:
        raw = constraints.get(key)
        if raw is None:
            return
        need = float(raw)
        if want_min and actual < need:
            unmet.append(key)
        if not want_min and actual > need:
            unmet.append(key)

    _gap("min_ergonomics", ergo, True)
    _gap("max_recoil_sum", recoil_sum, False)
    _gap("max_weight", weight, False)
    _gap("min_mag_capacity", mag, True)
    max_mag = constraints.get("max_mag_capacity")
    if max_mag is not None and (mag <= 0 or mag > float(max_mag)):
        unmet.append("max_mag_capacity")
    _gap("min_sighting_range", sight, True)
    conflicts = list(stats.get("conflicts") or [])
    ok = (
        not missing_items
        and not missing_categories
        and not unmet
        and not conflicts
    )
    return {
        "ok": ok,
        "stats": stats,
        "missing_items": missing_items,
        "missing_categories": missing_categories,
        "unmet_constraints": unmet,
        "conflicts": conflicts,
        "recoil_sum": recoil_sum,
    }


def _group_ids(group: list[dict[str, Any]]) -> set[str]:
    return {_named_id(row) for row in group if _named_id(row)}


def _find_place(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    installed: dict[str, str],
    item_id: str,
) -> tuple[str, dict[str, str]] | None:
    slots = _reachable_slots(index, gun, installed)
    for slot in slots:
        if item_id in slot.allowed_ids:
            return slot.id, installed
    for slot in slots:
        for cand_id in slot.allowed_ids:
            cand = index.items.get(cand_id)
            if not cand:
                continue
            for child in cand.slots:
                if item_id in child.allowed_ids:
                    nxt = _set_item(index, installed, slot.id, cand_id)
                    return child.id, nxt
    return None


def _place_item(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    installed: dict[str, str],
    item_id: str,
) -> dict[str, str] | None:
    found = _find_place(index, gun, installed, item_id)
    if found is None:
        return None
    slot_id, base = found
    return _set_item(index, base, slot_id, item_id)


def _candidate_ids(slot: wb.WbSlot, index: wb.WorkbenchIndex) -> list[str]:
    scored: list[tuple[float, float, float, str]] = []
    for item_id in slot.allowed_ids:
        item = index.items.get(item_id)
        if not item:
            continue
        scored.append((item.recoil_mod, -item.ergo, item.weight, item_id))
    scored.sort()
    return [row[3] for row in scored[:_CANDIDATES_PER_SLOT]]


def _score_state(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    installed: dict[str, str],
    spec: dict[str, Any],
    ammo_id: str | None,
) -> tuple:
    check = evaluate_build(index, gun, installed, spec, ammo_id)
    stats = check["stats"]
    return (
        len(check["missing_items"]),
        len(check["missing_categories"]),
        len(check["conflicts"]),
        len(check["unmet_constraints"]),
        int(stats.get("price_rub") or 10**9),
        -float(stats.get("ergonomics") or 0),
        int(check.get("recoil_sum") or 0),
    )


def solve_spec(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    spec: dict[str, Any],
    ammo_id: str | None = None,
) -> dict[str, Any]:
    ammo = wb.compatible_ammo_id(gun, ammo_id) or (gun.default_ammo_id or None)
    installed = wb._pairs_map(wb.map_factory_pairs(index, gun.id))
    for row in spec.get("required_items") or []:
        ident = _named_id(row)
        if not ident:
            continue
        if ident in set(_installed_ids(index, gun, installed)):
            continue
        nxt = _place_item(index, gun, installed, ident)
        if nxt is None:
            name = str(row.get("name") or ident)
            return {
                "status": "infeasible",
                "reason": f"无法安装必装件 {name}",
                "pairs": _pairs_list(installed),
                "checklist": evaluate_build(index, gun, installed, spec, ammo),
            }
        installed = nxt
    for group in spec.get("required_category_groups") or []:
        ids = _group_ids(group)
        if not ids:
            continue
        present_items = [
            index.items[iid]
            for iid in _installed_ids(index, gun, installed)
            if iid in index.items
        ]
        if any(_item_matches_group(item, ids) for item in present_items):
            continue
        options: list[tuple[float, float, str, str]] = []
        for slot in _reachable_slots(index, gun, installed):
            for item_id in slot.allowed_ids:
                item = index.items.get(item_id)
                if not item or not _item_matches_group(item, ids):
                    continue
                options.append((item.recoil_mod, -item.ergo, slot.id, item_id))
        options.sort()
        placed = False
        for _rec, _ergo, slot_id, item_id in options:
            nxt = _set_item(index, installed, slot_id, item_id)
            if item_id in set(_installed_ids(index, gun, nxt)):
                installed = nxt
                placed = True
                break
        if not placed:
            label = " / ".join(
                str(row.get("name") or row.get("id") or "") for row in group
            )
            return {
                "status": "infeasible",
                "reason": f"无法安装类别 {label}".strip(),
                "pairs": _pairs_list(installed),
                "checklist": evaluate_build(index, gun, installed, spec, ammo),
            }

    best = dict(installed)
    best_score = _score_state(index, gun, best, spec, ammo)
    for _ in range(_SEARCH_ITERS):
        improved = False
        slots = _reachable_slots(index, gun, best)
        for slot in slots:
            current = best.get(slot.id, "")
            candidates = _candidate_ids(slot, index)
            if current and current not in candidates:
                candidates.insert(0, current)
            if not slot.required:
                trial_ids = [""] + candidates
            else:
                trial_ids = candidates
            for item_id in trial_ids:
                if item_id == current:
                    continue
                nxt = _set_item(index, best, slot.id, item_id or None)
                score = _score_state(index, gun, nxt, spec, ammo)
                if score < best_score:
                    best = nxt
                    best_score = score
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break

    check = evaluate_build(index, gun, best, spec, ammo)
    status = "optimal" if check["ok"] else "infeasible"
    reason = ""
    if not check["ok"]:
        bits: list[str] = []
        if check["missing_items"]:
            bits.append("缺少必装件")
        if check["missing_categories"]:
            bits.append("缺少指定类别")
        if check["unmet_constraints"]:
            bits.append("属性未达标")
        if check["conflicts"]:
            bits.append("配件冲突")
        reason = "、".join(bits) or "当前过滤下无解"
    return {
        "status": status,
        "reason": reason,
        "pairs": _pairs_list(best),
        "checklist": check,
        "ammo_id": ammo,
    }


def solve_gunsmith_task(
    db: Session,
    task_id: str,
    objective_id: str | None = None,
    ammo_id: str | None = None,
) -> dict[str, Any]:
    spec = get_gunsmith_task(db, task_id, objective_id)
    if not spec.get("loadable"):
        raise wb.TarkovWorkbenchError("图鉴里没有这把枪", status_code=404)
    index = wb.load_index(db)
    gun = wb._require_gun(index, spec["weapon_id"])
    result = solve_spec(index, gun, spec, ammo_id)
    stats = (result.get("checklist") or {}).get("stats") or {}
    return {
        "status": result["status"],
        "reason": result.get("reason") or "",
        "task_id": spec["task_id"],
        "objective_id": spec["objective_id"],
        "weapon_id": gun.id,
        "ammo_id": result.get("ammo_id") or ammo_id,
        "pairs": [{"slot_id": a, "item_id": b} for a, b in result["pairs"]],
        "stats": stats,
        "checklist": result.get("checklist") or {},
    }
