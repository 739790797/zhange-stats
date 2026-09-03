"""tarkov-data-overlay：原样落库，读 json.tarkov.dev raw 时内存合入。

不写进 tasks/items/crafts raw；不落第三份合并表。overlay 的 locales 不覆盖 zh。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tarkov import upstream as upstream_svc
from app.services.tarkov.game_mode import cache_key, json_api_prefix
from app.services.tarkov.http import download_bytes_with_meta

logger = logging.getLogger(__name__)

OVERLAY_RESOURCE = "overlay"
SOURCE_OVERLAY = "tarkov-data-overlay"
OVERLAY_URL = (
    "https://cdn.jsdelivr.net/gh/tarkovtracker-org/tarkov-data-overlay"
    "@main/dist/overlay.json"
)
DOWNLOAD_TIMEOUT = 60

_TASK_PATCH_SKIP = frozenset({"objectives", "objectivesAdd", "traderRequirements", "disabled"})


class TarkovOverlayError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def overlay_mode_key(game_mode: str | None = None) -> str:
    """overlay.modes 键：战鸽 pvp → regular，pve → pve。"""
    return json_api_prefix(game_mode)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _req_id(row: dict[str, Any], *, fallback: str) -> str:
    ident = str(row.get("id") or "").strip()
    return ident or fallback


def _tasks_parent(payload: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    nested = payload.get("tasks")
    if isinstance(nested, (dict, list)):
        return payload, "tasks"
    data = payload.get("data")
    if isinstance(data, dict):
        nested = data.get("tasks")
        if isinstance(nested, (dict, list)):
            return data, "tasks"
    return None


def _tasks_map_from(blob: Any) -> dict[str, dict[str, Any]]:
    if isinstance(blob, dict):
        return {str(k): v for k, v in blob.items() if isinstance(v, dict)}
    if isinstance(blob, list):
        out: dict[str, dict[str, Any]] = {}
        for raw in blob:
            if not isinstance(raw, dict):
                continue
            ident = str(raw.get("id") or "").strip()
            if ident:
                out[ident] = raw
        return out
    return {}


def _live_items_map(payload: dict[str, Any]) -> dict[str, Any] | None:
    items_blob = payload.get("items")
    if isinstance(items_blob, dict):
        data = items_blob.get("data") if isinstance(items_blob.get("data"), dict) else items_blob
        if not isinstance(data, dict):
            return None
        items = data.get("items") if isinstance(data.get("items"), dict) else data
        return items if isinstance(items, dict) else None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else None
    if not isinstance(data, dict):
        return None
    items = data.get("items") if isinstance(data.get("items"), dict) else data
    return items if isinstance(items, dict) else None


def _live_crafts_list(payload: dict[str, Any]) -> list[Any] | None:
    blob = payload.get("crafts")
    if isinstance(blob, list):
        return blob
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("crafts"), list):
        return data["crafts"]
    return None


def _section(overlay: dict[str, Any], key: str, *, mode_key: str) -> dict[str, Any]:
    shared = _as_dict(overlay.get(key))
    mode_blob = _as_dict(_as_dict(overlay.get("modes")).get(mode_key)).get(key)
    return {**shared, **_as_dict(mode_blob)}


def _apply_objectives(base: Any, override: dict[str, Any]) -> list[Any]:
    out: list[Any] = []
    patches = override.get("objectives")
    patch_map = patches if isinstance(patches, dict) else {}
    for obj in _as_list(base):
        if not isinstance(obj, dict):
            continue
        oid = str(obj.get("id") or "")
        patch = patch_map.get(oid) if oid else None
        out.append({**obj, **patch} if isinstance(patch, dict) else dict(obj))
    added = override.get("objectivesAdd")
    if isinstance(added, list):
        out.extend(row for row in added if isinstance(row, dict))
    elif isinstance(added, dict):
        out.extend(row for row in added.values() if isinstance(row, dict))
    return out


def _apply_trader_requirements(base: Any, override_reqs: Any) -> list[Any]:
    if not isinstance(override_reqs, list):
        return _as_list(base)
    if not override_reqs:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in _as_list(base):
        if not isinstance(row, dict):
            continue
        ident = _req_id(row, fallback=f"overlay.anon.{len(order)}")
        by_id[ident] = dict(row)
        order.append(ident)
    for req in override_reqs:
        if not isinstance(req, dict):
            continue
        ident = str(req.get("id") or "").strip()
        if ident and ident in by_id:
            by_id[ident] = {**by_id[ident], **req}
            continue
        if not ident:
            ident = f"overlay.anon.{len(order)}"
        by_id[ident] = {**by_id[ident], **req} if ident in by_id else dict(req)
        if ident not in order:
            order.append(ident)
    return [by_id[i] for i in order]


def _apply_task_fields(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in _TASK_PATCH_SKIP:
            continue
        result[key] = value
    if "objectives" in override or "objectivesAdd" in override:
        result["objectives"] = _apply_objectives(base.get("objectives"), override)
    if "traderRequirements" in override:
        result["traderRequirements"] = _apply_trader_requirements(
            base.get("traderRequirements") or base.get("traderLevelRequirements"),
            override["traderRequirements"],
        )
    return result


def _apply_tasks(payload: dict[str, Any], overlay: dict[str, Any], mode_key: str) -> dict[str, Any]:
    additions = _section(overlay, "tasksAdd", mode_key=mode_key)
    overrides = _section(overlay, "tasks", mode_key=mode_key)
    if not additions and not overrides:
        return payload
    parent = _tasks_parent(payload)
    if parent is None:
        return payload
    holder, key = parent
    tasks = _tasks_map_from(holder.get(key))
    for tid, row in additions.items():
        if not isinstance(row, dict):
            continue
        if tid not in tasks:
            added = dict(row)
            added.setdefault("id", tid)
            tasks[tid] = added
    drop: list[str] = []
    for tid, base in list(tasks.items()):
        patch = overrides.get(tid)
        if not isinstance(patch, dict) or not patch:
            continue
        if patch.get("disabled") is True:
            drop.append(tid)
            continue
        tasks[tid] = _apply_task_fields(base, patch)
    for tid in drop:
        tasks.pop(tid, None)
    holder[key] = tasks
    return payload


def _apply_items(payload: dict[str, Any], overlay: dict[str, Any], mode_key: str) -> dict[str, Any]:
    items = _live_items_map(payload)
    if items is None:
        return payload
    additions = _section(overlay, "itemsAdd", mode_key=mode_key)
    for iid, row in additions.items():
        if not isinstance(row, dict) or iid in items:
            continue
        added = dict(row)
        added.setdefault("id", iid)
        items[iid] = added
    return payload


def _apply_crafts(payload: dict[str, Any], overlay: dict[str, Any], mode_key: str) -> dict[str, Any]:
    crafts = _live_crafts_list(payload)
    if crafts is None:
        return payload
    existing = {
        str(row.get("id") or "").strip()
        for row in crafts
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    additions = _section(overlay, "craftsAdd", mode_key=mode_key)
    for cid, row in additions.items():
        if not isinstance(row, dict):
            continue
        ident = str(row.get("id") or cid).strip()
        if not ident or ident in existing:
            continue
        added = dict(row)
        added.setdefault("id", ident)
        crafts.append(added)
        existing.add(ident)
    return payload


def apply_overlay(
    resource: str,
    payload: dict[str, Any],
    overlay: dict[str, Any] | None,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    """把 overlay 合进已解码的 json.tarkov.dev payload。无 overlay 时返回原对象。"""
    if not overlay or not payload:
        return payload
    mode_key = overlay_mode_key(game_mode)
    if resource == "tasks":
        return _apply_tasks(payload, overlay, mode_key)
    if resource == "items":
        return _apply_items(payload, overlay, mode_key)
    if resource == "crafts":
        return _apply_crafts(payload, overlay, mode_key)
    return payload


def download_overlay() -> tuple[dict[str, Any], str | None]:
    raw, upstream_at = download_bytes_with_meta(
        OVERLAY_URL,
        timeout=DOWNLOAD_TIMEOUT,
        error_cls=TarkovOverlayError,
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovOverlayError("overlay 解析失败") from exc
    if not isinstance(payload, dict) or not payload:
        raise TarkovOverlayError("overlay 为空")
    return payload, upstream_at


def sync_overlay(db: Session) -> dict[str, Any]:
    payload, upstream_at = download_overlay()
    logger.info("tarkov overlay dump ok (%s)", json_api_prefix())
    return persist_overlay(db, payload, upstream_at=upstream_at)


def persist_overlay(
    db: Session,
    payload: dict[str, Any],
    *,
    upstream_at: str | None = None,
) -> dict[str, Any]:
    return upstream_svc.persist_raw(
        db,
        OVERLAY_RESOURCE,
        payload,
        source=SOURCE_OVERLAY,
        note=f"{SOURCE_OVERLAY} dist/overlay.json",
        upstream_at=upstream_at,
    )


def load_overlay(db: Session) -> dict[str, Any] | None:
    """缺表/查库失败时当没有 overlay，避免物品 handbook 填充整条失败。"""
    try:
        payload = upstream_svc.load_raw(db, OVERLAY_RESOURCE)
    except Exception as exc:
        logger.warning("tarkov overlay raw unavailable: %s", exc)
        return None
    return payload if isinstance(payload, dict) and payload else None


def overlay_cache_token(db: Session) -> str:
    try:
        row = upstream_svc.load_raw_row(db, OVERLAY_RESOURCE)
    except Exception as exc:
        logger.warning("tarkov overlay cache token unavailable: %s", exc)
        return ""
    if row is None or not row.synced_at:
        return ""
    return row.synced_at.isoformat()


def parsed_cache_key(db: Session, resource_synced: str | None) -> str:
    return cache_key(resource_synced or "", overlay_cache_token(db))


def apply_loaded_overlay(
    db: Session,
    resource: str,
    payload: dict[str, Any],
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    return apply_overlay(resource, payload, load_overlay(db), game_mode=game_mode)
