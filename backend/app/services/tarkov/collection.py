"""塔科夫 3×4 收集：从收集者任务投影需上交道具，供个人中心格子勾选。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov import items as items_svc
from app.services.tarkov import tasks as tasks_svc

COLLECTOR_NORMALIZED = "collector"
COLLECTOR_NAMES = frozenset({"收集者", "collector"})
COLLECT_OBJECTIVE_TYPES = frozenset(
    {"giveItem", "findItem", "giveQuestItem", "findQuestItem"}
)
GRID_WIDTH = 3
GRID_HEIGHT = 4


class TarkovCollectionError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _norm_name(raw: str | None) -> str:
    return str(raw or "").strip().lower()


def is_collector_task(row: dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    slug = _norm_name(
        row.get("normalized_name") or row.get("normalizedName")
    )
    if slug == COLLECTOR_NORMALIZED:
        return True
    return _norm_name(row.get("name")) in COLLECTOR_NAMES


def find_collector_task_id(rows: list[dict[str, Any]]) -> str:
    named = ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        ident = str(row.get("id") or "").strip()
        if not ident:
            continue
        slug = _norm_name(row.get("normalized_name") or row.get("normalizedName"))
        if slug == COLLECTOR_NORMALIZED:
            return ident
        if not named and _norm_name(row.get("name")) in COLLECTOR_NAMES:
            named = ident
    return named


def pick_collector_raw(tasks: dict[str, Any]) -> dict[str, Any] | None:
    named: dict[str, Any] | None = None
    for raw in tasks.values():
        if not isinstance(raw, dict):
            continue
        slug = _norm_name(raw.get("normalizedName") or raw.get("normalized_name"))
        if slug == COLLECTOR_NORMALIZED:
            return raw
        if named is None and _norm_name(raw.get("name")) in COLLECTOR_NAMES:
            named = raw
    return named


def _as_size(value: Any, default: int = 1) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return default
    return size if size > 0 else default


def extract_collection_items(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """从已投影的任务详情抽出需收集道具，保目标出现顺序。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for obj in detail.get("objectives") or []:
        if not isinstance(obj, dict):
            continue
        if obj.get("optional"):
            continue
        if str(obj.get("type") or "") not in COLLECT_OBJECTIVE_TYPES:
            continue
        fir = obj.get("found_in_raid")
        count = _as_size(obj.get("count"), 1)
        objective_id = str(obj.get("id") or "").strip()
        for ref in obj.get("items") or []:
            if not isinstance(ref, dict):
                continue
            ident = str(ref.get("id") or "").strip()
            if not ident or ident in seen:
                continue
            seen.add(ident)
            types = ref.get("types") if isinstance(ref.get("types"), list) else []
            handbook_ids = (
                ref.get("handbook_ids")
                if isinstance(ref.get("handbook_ids"), list)
                else []
            )
            out.append(
                {
                    "id": ident,
                    "name": str(ref.get("name") or ident).strip() or ident,
                    "short_name": str(ref.get("short_name") or "").strip(),
                    "icon_link": str(ref.get("icon_link") or "").strip(),
                    "types": [str(t) for t in types if t is not None and str(t).strip()],
                    "handbook_ids": [
                        str(t).strip()
                        for t in handbook_ids
                        if t is not None and str(t).strip()
                    ],
                    "width": _as_size(ref.get("width"), 1),
                    "height": _as_size(ref.get("height"), 1),
                    "found_in_raid": bool(fir) if fir is not None else None,
                    "count": count,
                    "objective_id": objective_id,
                }
            )
    return out


def apply_catalog_hits(
    items: list[dict[str, Any]],
    hits: dict[str, dict[str, Any]],
) -> None:
    for item in items:
        hit = hits.get(str(item.get("id") or ""))
        if not isinstance(hit, dict):
            continue
        name = str(hit.get("name") or "").strip()
        if name:
            item["name"] = name
        short_name = str(hit.get("short_name") or "").strip()
        if short_name:
            item["short_name"] = short_name
        icon = str(hit.get("icon_link") or "").strip()
        if icon:
            item["icon_link"] = icon
        types = hit.get("types") if isinstance(hit.get("types"), list) else []
        if types:
            item["types"] = [str(t) for t in types if t is not None and str(t).strip()]
        handbook_ids = (
            hit.get("handbook_ids")
            if isinstance(hit.get("handbook_ids"), list)
            else []
        )
        if handbook_ids:
            item["handbook_ids"] = [
                str(t).strip()
                for t in handbook_ids
                if t is not None and str(t).strip()
            ]
        if hit.get("width") is not None:
            item["width"] = _as_size(hit.get("width"), 1)
        if hit.get("height") is not None:
            item["height"] = _as_size(hit.get("height"), 1)


def _empty_catalog(
    *,
    source: str | None = None,
    synced_at: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "task": None,
        "grid_width": GRID_WIDTH,
        "grid_height": GRID_HEIGHT,
        "items": [],
        "item_count": 0,
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }


def list_collection(db: Session) -> dict[str, Any]:
    try:
        items_svc.ensure_items(db)
    except items_svc.TarkovItemsError as exc:
        raise TarkovCollectionError(str(exc)) from exc
    try:
        source, rows, _locale, synced_at, note = tasks_svc.load_parsed_tasks(db)
    except tasks_svc.TarkovTasksError as exc:
        raise TarkovCollectionError(str(exc)) from exc
    task_id = find_collector_task_id(rows)
    if not task_id:
        return _empty_catalog(source=source, synced_at=synced_at, note=note)
    try:
        detail = tasks_svc.get_task_detail(db, task_id)
    except tasks_svc.TarkovTasksError as exc:
        raise TarkovCollectionError(str(exc)) from exc
    items = extract_collection_items(detail)
    wanted = {str(item.get("id") or "").strip() for item in items if item.get("id")}
    if wanted:
        apply_catalog_hits(
            items,
            tasks_svc._lookup_item_hits_from_catalog(db, wanted),
        )
    return {
        "task": {
            "id": str(detail.get("id") or task_id),
            "name": str(detail.get("name") or "收集者"),
            "normalized_name": str(detail.get("normalized_name") or COLLECTOR_NORMALIZED),
            "trader_slug": str(detail.get("trader_slug") or ""),
            "trader_name": str(detail.get("trader_name") or ""),
        },
        "grid_width": GRID_WIDTH,
        "grid_height": GRID_HEIGHT,
        "items": items,
        "item_count": len(items),
        "source": source,
        "synced_at": synced_at,
        "note": note,
    }
