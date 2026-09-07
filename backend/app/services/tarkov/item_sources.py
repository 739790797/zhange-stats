"""物品来源 / 用途：items dump 没有 craftsFor、usedInTasks 等反查字段。

json.tarkov.dev 的物品对象只有买价/卖价等正向字段；GraphQL 的
bartersFor / craftsFor / receivedFromTasks / bartersUsing / craftsUsing /
usedInTasks / droppedBy 是 tarkov-api 运行时从 crafts / barters / tasks /
hideout / maps.mobs 算的。此处同样只扫已落库 dump，不打 GraphQL。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov import guides as guides_svc
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov.guides import TarkovGuidesError
from app.services.tarkov.overlay import parsed_cache_key
from app.services.tarkov.tasks import TarkovTasksError

logger = logging.getLogger(__name__)

QUEST_KIND_START = "start"
QUEST_KIND_FINISH = "finish"

_task_source_cache: tuple[str, list[dict[str, Any]], dict[str, Any]] | None = None
_task_source_lock = threading.Lock()


def empty_item_sources() -> dict[str, Any]:
    return {"barters": [], "crafts": [], "quest_rewards": [], "drops": []}


def empty_item_uses() -> dict[str, Any]:
    return {"barters": [], "crafts": [], "hideout": [], "tasks": []}


def _as_count(value: Any, default: float = 1) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return default
    if number == int(number):
        return int(number)
    return number


def _item_id(raw: Any) -> str:
    if isinstance(raw, dict):
        nested = raw.get("item")
        if nested is not None:
            ident = tasks_svc._id_of(nested)
            if ident:
                return ident
        return tasks_svc._id_of(raw)
    return str(raw or "").strip()


def _nested_reward_rows(row: dict[str, Any]) -> list[Any]:
    blob = row.get("contains")
    if not isinstance(blob, list):
        blob = row.get("containsItems")
    return blob if isinstance(blob, list) else []


def _reward_count_for_item(blob: Any, item_id: str) -> float | None:
    if not isinstance(blob, dict) or not item_id:
        return None
    total = 0.0
    hit = False
    for row in blob.get("items") or []:
        if not isinstance(row, dict):
            if _item_id(row) == item_id:
                hit = True
                total += 1
            continue
        count = _as_count(row.get("count"), 1)
        if _item_id(row) == item_id:
            hit = True
            total += count
        for inner in _nested_reward_rows(row):
            if not isinstance(inner, dict):
                if _item_id(inner) == item_id:
                    hit = True
                    total += 1
                continue
            if _item_id(inner) == item_id:
                hit = True
                total += _as_count(inner.get("count") or inner.get("quantity"), 1)
    if not hit:
        return None
    return _as_count(total, 1)


def _copy_trade_row(row: dict[str, Any], *, product_key: str) -> dict[str, Any]:
    product = row.get(product_key)
    return {
        **row,
        "required_items": [
            dict(req) if isinstance(req, dict) else req
            for req in (row.get("required_items") or [])
        ],
        product_key: dict(product) if isinstance(product, dict) else product,
    }


def _task_label(raw: dict[str, Any], locale: dict[str, Any]) -> str:
    task_id = str(raw.get("id") or "").strip()
    loc_name = tasks_svc._locale_lookup(locale, f"{task_id} name", f"{task_id} Name")
    name = loc_name or str(raw.get("name") or "").strip()
    if task_id and tasks_svc._is_placeholder_name(task_id, name):
        slug = str(raw.get("normalizedName") or "").strip()
        return slug.replace("-", " ").title() if slug else task_id
    return name or task_id


def _quest_reward_row(
    raw: dict[str, Any],
    locale: dict[str, Any],
    *,
    kind: str,
    count: float,
) -> dict[str, Any]:
    task_id = str(raw.get("id") or "").strip()
    trader_raw = raw.get("trader")
    trader_id = tasks_svc._id_of(trader_raw)
    slug, tname = tasks_svc.trader_info(trader_id, trader_raw)
    return {
        "id": task_id,
        "name": _task_label(raw, locale),
        "trader_id": trader_id,
        "trader_slug": slug,
        "trader_name": tname.split("（", 1)[0] if tname else slug or trader_id,
        "kind": kind,
        "count": count,
    }


def collect_item_sources(
    item_id: str,
    *,
    barters: list[dict[str, Any]] | None = None,
    crafts: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    locale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从已 parse 的交换 / 制作、以及任务 raw 反查该物品的获取途径。"""
    ident = (item_id or "").strip()
    out = empty_item_sources()
    if not ident:
        return out
    loc = locale if isinstance(locale, dict) else {}

    for row in barters or []:
        if not isinstance(row, dict):
            continue
        offered = row.get("offered_item") if isinstance(row.get("offered_item"), dict) else {}
        if str(offered.get("id") or "").strip() != ident:
            continue
        out["barters"].append(_copy_trade_row(row, product_key="offered_item"))

    for row in crafts or []:
        if not isinstance(row, dict):
            continue
        product = row.get("product_item") if isinstance(row.get("product_item"), dict) else {}
        if str(product.get("id") or "").strip() != ident:
            continue
        out["crafts"].append(_copy_trade_row(row, product_key="product_item"))

    for raw in tasks or []:
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("id") or "").strip()
        if not task_id:
            continue
        start_count = _reward_count_for_item(raw.get("startRewards"), ident)
        if start_count is not None:
            out["quest_rewards"].append(
                _quest_reward_row(
                    raw, loc, kind=QUEST_KIND_START, count=start_count
                )
            )
        finish_count = _reward_count_for_item(raw.get("finishRewards"), ident)
        if finish_count is not None:
            out["quest_rewards"].append(
                _quest_reward_row(
                    raw, loc, kind=QUEST_KIND_FINISH, count=finish_count
                )
            )

    out["barters"].sort(
        key=lambda row: (
            str(row.get("trader_name") or ""),
            int(row.get("min_trader_level") or 0),
            str(row.get("id") or ""),
        )
    )
    out["crafts"].sort(
        key=lambda row: (
            str(row.get("station_name") or ""),
            int(row.get("level") or 0),
            str(row.get("id") or ""),
        )
    )
    kind_rank = {QUEST_KIND_FINISH: 0, QUEST_KIND_START: 1}
    out["quest_rewards"].sort(
        key=lambda row: (
            kind_rank.get(str(row.get("kind") or ""), 9),
            str(row.get("trader_slug") or ""),
            str(row.get("name") or ""),
            str(row.get("id") or ""),
        )
    )
    return out


def _objective_note(obj: dict[str, Any], locale: dict[str, Any]) -> str:
    oid = str(obj.get("id") or "").strip()
    note = str(obj.get("description") or "").strip()
    resolved = tasks_svc._resolve_obj_description(obj, locale)
    if resolved:
        note = resolved
    if not note or note == oid:
        return ""
    if oid and tasks_svc._is_placeholder_name(oid, note):
        return ""
    if note.endswith(" description") or note.endswith(" Description"):
        return ""
    return note


def _iter_nested_item_ids(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, list):
        for row in value:
            out.extend(_iter_nested_item_ids(row))
        return out
    ident = _item_id(value)
    if ident:
        out.append(ident)
    return out


def _objective_mentions_item(obj: dict[str, Any], item_id: str) -> bool:
    if not item_id or not isinstance(obj, dict):
        return False
    for raw in tasks_svc._objective_item_values(obj, {}):
        if _item_id(raw) == item_id:
            return True
    for key in ("containsOne", "containsAll", "usingWeapon"):
        if item_id in _iter_nested_item_ids(obj.get(key)):
            return True
    for outfit in obj.get("wearing") or []:
        if item_id in _iter_nested_item_ids(outfit):
            return True
    for group in obj.get("usingWeaponMods") or []:
        if item_id in _iter_nested_item_ids(group):
            return True
    groups = obj.get("requiredKeys")
    if groups is None:
        groups = obj.get("required_keys")
    if item_id in _iter_nested_item_ids(groups):
        return True
    return False


def _task_needs_item_keys(raw: dict[str, Any], item_id: str) -> bool:
    for needed in raw.get("neededKeys") or raw.get("needed_keys") or []:
        if not isinstance(needed, dict):
            continue
        if item_id in _iter_nested_item_ids(needed.get("keys")):
            return True
    return False


def _task_use_row(
    raw: dict[str, Any],
    locale: dict[str, Any],
    item_id: str,
) -> dict[str, Any] | None:
    notes: list[str] = []
    seen_notes: set[str] = set()
    total = 0.0
    counted = False
    hit = _task_needs_item_keys(raw, item_id)
    for obj in raw.get("objectives") or []:
        if not isinstance(obj, dict) or not _objective_mentions_item(obj, item_id):
            continue
        hit = True
        note = _objective_note(obj, locale)
        if note and note not in seen_notes and len(notes) < 6:
            seen_notes.add(note)
            notes.append(note)
        count = obj.get("count")
        if count is None:
            continue
        try:
            number = float(count)
        except (TypeError, ValueError):
            continue
        if number > 0:
            counted = True
            total += number
    if not hit:
        return None
    row = _quest_reward_row(raw, locale, kind="require", count=1)
    row.pop("kind", None)
    row["notes"] = notes
    if counted:
        row["count"] = _as_count(total, 1)
    else:
        row.pop("count", None)
    return row


def _hideout_use_rows(
    stations: list[dict[str, Any]] | None,
    item_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for station in stations or []:
        if not isinstance(station, dict):
            continue
        for level in station.get("levels") or []:
            if not isinstance(level, dict):
                continue
            total = 0.0
            hit = False
            for req in level.get("item_requirements") or []:
                if not isinstance(req, dict):
                    continue
                if str(req.get("id") or "").strip() != item_id:
                    continue
                hit = True
                total += _as_count(req.get("count"), 1)
            if not hit:
                continue
            out.append(
                {
                    "station_id": str(station.get("id") or ""),
                    "station_slug": str(station.get("slug") or ""),
                    "station_name": str(station.get("name") or ""),
                    "level": int(level.get("level") or 0),
                    "count": _as_count(total, 1),
                }
            )
    out.sort(
        key=lambda row: (
            str(row.get("station_name") or ""),
            int(row.get("level") or 0),
            str(row.get("station_slug") or ""),
        )
    )
    return out


def collect_item_uses(
    item_id: str,
    *,
    barters: list[dict[str, Any]] | None = None,
    crafts: list[dict[str, Any]] | None = None,
    stations: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    locale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从交换材料 / 制作材料 / 藏身处建造 / 任务目标反查该物品的用途。"""
    ident = (item_id or "").strip()
    out = empty_item_uses()
    if not ident:
        return out
    loc = locale if isinstance(locale, dict) else {}

    for row in barters or []:
        if not isinstance(row, dict):
            continue
        if not any(
            isinstance(req, dict) and str(req.get("id") or "").strip() == ident
            for req in (row.get("required_items") or [])
        ):
            continue
        out["barters"].append(_copy_trade_row(row, product_key="offered_item"))

    for row in crafts or []:
        if not isinstance(row, dict):
            continue
        if not any(
            isinstance(req, dict) and str(req.get("id") or "").strip() == ident
            for req in (row.get("required_items") or [])
        ):
            continue
        out["crafts"].append(_copy_trade_row(row, product_key="product_item"))

    out["hideout"] = _hideout_use_rows(stations, ident)

    for raw in tasks or []:
        if not isinstance(raw, dict):
            continue
        if not str(raw.get("id") or "").strip():
            continue
        hit = _task_use_row(raw, loc, ident)
        if hit:
            out["tasks"].append(hit)

    out["barters"].sort(
        key=lambda row: (
            str(row.get("trader_name") or ""),
            int(row.get("min_trader_level") or 0),
            str(row.get("id") or ""),
        )
    )
    out["crafts"].sort(
        key=lambda row: (
            str(row.get("station_name") or ""),
            int(row.get("level") or 0),
            str(row.get("id") or ""),
        )
    )
    out["tasks"].sort(
        key=lambda row: (
            str(row.get("trader_slug") or ""),
            str(row.get("name") or ""),
            str(row.get("id") or ""),
        )
    )
    return out


def _enrich_sources(db: Session, sources: dict[str, Any]) -> dict[str, Any]:
    needed: set[str] = set()
    for row in sources.get("barters") or []:
        needed |= guides_svc._collect_ids(row.get("required_items") or [])
        offered = row.get("offered_item") or {}
        if isinstance(offered, dict) and offered.get("id"):
            needed.add(str(offered["id"]))
    for row in sources.get("crafts") or []:
        needed |= guides_svc._collect_ids(row.get("required_items") or [])
        product = row.get("product_item") or {}
        if isinstance(product, dict) and product.get("id"):
            needed.add(str(product["id"]))
    items = guides_svc._lookup_items(db, needed)
    sources["barters"] = [
        {
            **row,
            "required_items": [
                guides_svc._enrich_item(req, items)
                for req in (row.get("required_items") or [])
                if isinstance(req, dict)
            ],
            "offered_item": guides_svc._enrich_item(
                row.get("offered_item") or {}, items
            ),
        }
        for row in (sources.get("barters") or [])
        if isinstance(row, dict)
    ]
    sources["crafts"] = [
        {
            **row,
            "required_items": [
                guides_svc._enrich_item(req, items)
                for req in (row.get("required_items") or [])
                if isinstance(req, dict)
            ],
            "product_item": guides_svc._enrich_item(
                row.get("product_item") or {}, items
            ),
        }
        for row in (sources.get("crafts") or [])
        if isinstance(row, dict)
    ]
    return sources


def _load_guide_rows(
    db: Session,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if guides_svc.get_hideout_raw(db) is None:
        return [], [], []
    try:
        _source, parsed, _synced, _note = guides_svc.load_parsed_guides(db)
    except TarkovGuidesError as exc:
        logger.warning("item sources guides unavailable: %s", exc)
        return [], [], []
    barters = parsed.get("barters") if isinstance(parsed.get("barters"), list) else []
    crafts = parsed.get("crafts") if isinstance(parsed.get("crafts"), list) else []
    stations = (
        parsed.get("stations") if isinstance(parsed.get("stations"), list) else []
    )
    return barters, crafts, stations


def _task_rows_from_payload(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    locale = tasks_svc._locale_map(payload)
    rows: list[dict[str, Any]] = []
    for tid, raw in tasks_svc._tasks_map(payload).items():
        if not isinstance(raw, dict):
            continue
        copied = dict(raw)
        copied["id"] = str(copied.get("id") or tid).strip()
        rows.append(copied)
    return rows, locale


def _load_task_rows(db: Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    global _task_source_cache
    raw_row = tasks_svc.get_tasks_raw(db)
    if raw_row is None:
        return [], {}
    synced = raw_row.synced_at.isoformat() if raw_row.synced_at else None
    key = parsed_cache_key(db, synced)
    with _task_source_lock:
        cached = _task_source_cache
        if cached is not None and cached[0] == key:
            return cached[1], cached[2]
    try:
        _source, payload, _synced, _note = tasks_svc._load_payload(db)
    except TarkovTasksError as exc:
        logger.warning("item sources tasks unavailable: %s", exc)
        return [], {}
    rows, locale = _task_rows_from_payload(payload)
    with _task_source_lock:
        _task_source_cache = (key, rows, locale)
    return rows, locale


def collect_item_drops(
    item_id: str,
    boss_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """从 maps/mobs 配装反查会掉这件物品的 Boss / 非 Boss。"""
    from app.services.tarkov.bosses import BOSS_KIND_BOSS, BOSS_KIND_ORDER, mob_loot_item_ids

    ident = (item_id or "").strip()
    if not ident:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in boss_rows or []:
        if not isinstance(row, dict):
            continue
        if ident not in mob_loot_item_ids(row):
            continue
        mob_id = str(row.get("id") or "").strip()
        slug = str(row.get("slug") or "").strip()
        key = slug or mob_id
        if not key or key in seen:
            continue
        seen.add(key)
        kind = str(row.get("kind") or BOSS_KIND_BOSS).strip() or BOSS_KIND_BOSS
        parents = row.get("parent_ids")
        out.append(
            {
                "id": mob_id,
                "slug": slug,
                "name": str(row.get("name") or slug or mob_id),
                "kind": kind,
                "maps_label": str(row.get("maps_label") or ""),
                "portrait_link": str(row.get("portrait_link") or ""),
                "parent_ids": [
                    str(parent).strip()
                    for parent in (parents if isinstance(parents, list) else [])
                    if str(parent).strip()
                ],
            }
        )
    out.sort(
        key=lambda row: (
            BOSS_KIND_ORDER.get(str(row.get("kind") or ""), 9),
            str(row.get("name") or "").lower(),
            str(row.get("slug") or ""),
        )
    )
    return out


def _load_boss_rows(db: Session) -> list[dict[str, Any]]:
    from app.services.tarkov import bosses as bosses_svc

    _source, rows, _synced, _note = bosses_svc.load_parsed_bosses(db)
    return rows


def attach_item_sources(db: Session, detail: dict[str, Any]) -> None:
    """物品详情反查来源与用途；缺 dump 时保持空列表，不挡详情页。"""
    detail["sources"] = empty_item_sources()
    detail["uses"] = empty_item_uses()
    item_id = str(detail.get("id") or "").strip()
    if not item_id:
        return
    try:
        barters, crafts, stations = _load_guide_rows(db)
        tasks, locale = _load_task_rows(db)
        detail["sources"] = _enrich_sources(
            db,
            collect_item_sources(
                item_id,
                barters=barters,
                crafts=crafts,
                tasks=tasks,
                locale=locale,
            ),
        )
        detail["uses"] = _enrich_sources(
            db,
            collect_item_uses(
                item_id,
                barters=barters,
                crafts=crafts,
                stations=stations,
                tasks=tasks,
                locale=locale,
            ),
        )
    except Exception:  # noqa: BLE001
        logger.warning("item sources unavailable", exc_info=True)
        return
    try:
        detail["sources"]["drops"] = collect_item_drops(item_id, _load_boss_rows(db))
    except Exception:  # noqa: BLE001
        logger.warning("item drop sources unavailable", exc_info=True)
        detail["sources"]["drops"] = []
