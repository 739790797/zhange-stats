"""逃离塔科夫攻略站全站搜索：物品 / 任务 / 商人 / BOSS（有 raw 才查，不回源）。"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.services.tarkov import bosses as bosses_svc
from app.services.tarkov import catalog as catalog_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import traders as traders_svc
from app.services.tarkov.items import TarkovItemsError
from app.services.tarkov.tasks import TarkovTasksError
from app.services.tarkov.traders import TarkovTradersError
from app.services.tarkov.bosses import TarkovBossesError

logger = logging.getLogger(__name__)

SEARCH_LIMIT = 10
_TOKEN_RE = re.compile(r"[0-9a-zA-Z]+|[\u4e00-\u9fff]+")
_COMPACT_RE = re.compile(r"[\s\-_.·•]+")


def compact_text(text: str) -> str:
    return _COMPACT_RE.sub("", (text or "").strip().lower())


def search_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def hit_rank(needle: str, *fields: str) -> int | None:
    """越小越靠前：0 精确压缩、1 前缀、2 包含、3 分词全中。"""
    compact_q = compact_text(needle)
    tokens = search_tokens(needle)
    if not compact_q and not tokens:
        return None
    best: int | None = None
    for field in fields:
        hay = str(field or "")
        if not hay:
            continue
        compact_h = compact_text(hay)
        lower_h = hay.lower()
        if compact_q and compact_h == compact_q:
            return 0
        if compact_q and compact_h.startswith(compact_q):
            best = 1 if best is None else min(best, 1)
            continue
        if compact_q and compact_q in compact_h:
            best = 2 if best is None else min(best, 2)
            continue
        if tokens and all(t in lower_h or t in compact_h for t in tokens):
            best = 3 if best is None else min(best, 3)
    return best


def pick_hits(
    rows: Iterable[dict[str, Any]],
    needle: str,
    fields: tuple[str, ...],
    *,
    limit: int = SEARCH_LIMIT,
) -> tuple[list[dict[str, Any]], int]:
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for row in rows:
        rank = hit_rank(needle, *(str(row.get(key) or "") for key in fields))
        if rank is None:
            continue
        name = str(row.get("name") or row.get("label") or "")
        scored.append((rank, name, row))
    scored.sort(key=lambda item: (item[0], item[1], str(item[2].get("id") or "")))
    total = len(scored)
    return [row for _rank, _name, row in scored[: max(0, limit)]], total


def _empty(q: str) -> dict[str, Any]:
    return {
        "q": q,
        "items": [],
        "tasks": [],
        "traders": [],
        "bosses": [],
        "item_count": 0,
        "task_count": 0,
        "trader_count": 0,
        "boss_count": 0,
    }


def _item_hit(row: dict[str, Any]) -> dict[str, Any]:
    short_name = str(row.get("short_name") or "")
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "extra": short_name,
        "icon_link": str(row.get("icon_link") or ""),
        "types": [str(t) for t in (row.get("types") or []) if t],
        "slug": "",
    }


def _task_hit(row: dict[str, Any]) -> dict[str, Any]:
    extra = " · ".join(
        part
        for part in (
            str(row.get("trader_name") or "").strip(),
            str(row.get("map_name") or "").strip(),
        )
        if part
    )
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "extra": extra,
        "icon_link": str(row.get("task_image_link") or ""),
        "types": [],
        "slug": "",
    }


def _trader_hit(row: dict[str, Any]) -> dict[str, Any]:
    chinese = str(row.get("chinese") or "").strip()
    english = str(row.get("english") or "").strip()
    extra = chinese if chinese else english
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or english or row.get("slug") or ""),
        "extra": extra,
        "icon_link": str(row.get("portrait_link") or ""),
        "types": [],
        "slug": str(row.get("slug") or ""),
    }


def _boss_search_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        alias = bosses_svc.NICKNAMES.get(str(row.get("slug") or ""), "")
        if alias:
            out.append({**row, "search_alias": alias})
        else:
            out.append(row)
    return out


def _boss_hit(row: dict[str, Any]) -> dict[str, Any]:
    extra = str(row.get("maps_label") or "").strip()
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "extra": extra,
        "icon_link": str(row.get("portrait_link") or ""),
        "types": [],
        "slug": str(row.get("slug") or ""),
    }


def _item_rows(db: Session) -> list[dict[str, Any]]:
    if items_svc.get_items_raw(db) is None:
        return []
    try:
        return catalog_svc.peek_catalog_items(db)
    except TarkovItemsError as exc:
        logger.warning("site search items skipped: %s", exc)
        return []


def _task_rows(db: Session) -> list[dict[str, Any]]:
    if tasks_svc.get_tasks_raw(db) is None:
        return []
    try:
        _source, rows, _locale, _synced, _note = tasks_svc.load_parsed_tasks(db)
        return rows
    except TarkovTasksError as exc:
        logger.warning("site search tasks skipped: %s", exc)
        return []


def _trader_rows(db: Session) -> list[dict[str, Any]]:
    if traders_svc.get_traders_raw(db) is None:
        return []
    try:
        return list(traders_svc.list_traders(db).get("items") or [])
    except TarkovTradersError as exc:
        logger.warning("site search traders skipped: %s", exc)
        return []


def _boss_rows(db: Session) -> list[dict[str, Any]]:
    if bosses_svc.get_maps_raw(db) is None:
        return []
    try:
        return _boss_search_rows(list(bosses_svc.list_bosses(db).get("items") or []))
    except TarkovBossesError as exc:
        logger.warning("site search bosses skipped: %s", exc)
        return []


def search_site(db: Session, q: str, *, limit: int = SEARCH_LIMIT) -> dict[str, Any]:
    needle = (q or "").strip()
    if not needle:
        return _empty("")

    items, item_count = pick_hits(
        _item_rows(db),
        needle,
        ("name", "short_name", "id"),
        limit=limit,
    )
    tasks, task_count = pick_hits(
        _task_rows(db),
        needle,
        ("name", "normalized_name", "id"),
        limit=limit,
    )
    traders, trader_count = pick_hits(
        _trader_rows(db),
        needle,
        ("name", "english", "chinese", "slug", "id"),
        limit=limit,
    )
    bosses, boss_count = pick_hits(
        _boss_rows(db),
        needle,
        ("name", "search_alias", "slug", "id", "maps_label"),
        limit=limit,
    )
    return {
        "q": needle,
        "items": [_item_hit(row) for row in items],
        "tasks": [_task_hit(row) for row in tasks],
        "traders": [_trader_hit(row) for row in traders],
        "bosses": [_boss_hit(row) for row in bosses],
        "item_count": item_count,
        "task_count": task_count,
        "trader_count": trader_count,
        "boss_count": boss_count,
    }
