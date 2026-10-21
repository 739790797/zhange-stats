"""tarkov-data-overlay：原样落库，读 json.tarkov.dev raw 时内存合入。

不写进 tasks/items/crafts raw；不落第三份合并表。
只合 overlay 的 tasksAdd / tasks 补丁 / disabled，以及 dump requiredPrestige id → overlay prestige 表。
不套 overlay locales，不把另一模式 dump 的任务抄进来。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core import timeutil
from app.services.tarkov import items as items_svc
from app.services.tarkov import upstream as upstream_svc
from app.services.tarkov.game_mode import cache_key, json_api_prefix, parse_game_mode
from app.services.upstream_repos import REPO_TARKOV_OVERLAY, RepoError, ensure_repo, read_repo_bytes

logger = logging.getLogger(__name__)

OVERLAY_RESOURCE = "overlay"
SOURCE_OVERLAY = "tarkov-data-overlay"
OVERLAY_REL = "dist/overlay.json"
# 上一份好 overlay 超过这个年龄就在同步结果里标 stale
OVERLAY_STALE_AFTER_SEC = 45 * 24 * 3600
# 合入逻辑变更时递增，打穿进程内 parse cache（物品/制作/任务共用）
OVERLAY_PARSE_REV = "upstream-only-v1"

_TASK_PATCH_SKIP = frozenset({"objectives", "objectivesAdd", "traderRequirements", "disabled"})

# 最近一次成功下载：给同步结果报新鲜度；进程重启后退化成库里的 synced_at
_last_success: dict[str, Any] = {}


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
    """items payload 里的物品表；空 → None（overlay 的 itemsAdd 没处可合）。"""
    return items_svc.items_container(payload) or None


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


def _prestige_by_id(overlay: dict[str, Any], mode_key: str) -> dict[str, Any]:
    """声望档只写在 modes.regular 时，PVE 也要能解开 dump 的 requiredPrestige id。"""
    shared = _as_dict(overlay.get("prestige"))
    modes = _as_dict(overlay.get("modes"))
    regular = _as_dict(_as_dict(modes.get("regular")).get("prestige"))
    current = _as_dict(_as_dict(modes.get(mode_key)).get("prestige"))
    return {**shared, **regular, **current}


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


def _hydrate_required_prestige(
    tasks: dict[str, dict[str, Any]],
    prestige_by_id: dict[str, Any],
) -> None:
    """dump 常把 requiredPrestige 写成声望 id；补上 prestigeLevel 才能分同名线。"""
    if not prestige_by_id:
        return
    for raw in tasks.values():
        blob = raw.get("requiredPrestige")
        if blob is None:
            continue
        if isinstance(blob, dict):
            if blob.get("prestigeLevel") is not None or blob.get("prestige_level") is not None:
                continue
            ident = str(blob.get("id") or "").strip()
            hit = prestige_by_id.get(ident) if ident else None
            if not isinstance(hit, dict):
                continue
            raw["requiredPrestige"] = {**hit, **blob, "id": ident}
            continue
        ident = str(blob).strip()
        if not ident:
            continue
        hit = prestige_by_id.get(ident)
        if isinstance(hit, dict):
            merged = dict(hit)
            merged["id"] = ident
            raw["requiredPrestige"] = merged
        else:
            raw["requiredPrestige"] = {"id": ident}


def _apply_tasks(payload: dict[str, Any], overlay: dict[str, Any], mode_key: str) -> dict[str, Any]:
    additions = _section(overlay, "tasksAdd", mode_key=mode_key)
    overrides = _section(overlay, "tasks", mode_key=mode_key)
    prestige_by_id = _prestige_by_id(overlay, mode_key)
    if not additions and not overrides and not prestige_by_id:
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
    _hydrate_required_prestige(tasks, prestige_by_id)
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


def download_overlay(
    *,
    on_bytes: Callable[[int, int | None], None] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """读本地 tarkov-data-overlay 克隆。失败抛错，调用方保留上一份好数据。"""
    try:
        ensure_repo(REPO_TARKOV_OVERLAY)
        raw = read_repo_bytes(REPO_TARKOV_OVERLAY, OVERLAY_REL)
    except RepoError as exc:
        record_overlay_failure(exc.message)
        raise TarkovOverlayError(exc.message) from exc
    if on_bytes is not None:
        on_bytes(len(raw), len(raw))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        record_overlay_failure("overlay 解析失败")
        raise TarkovOverlayError("overlay 解析失败") from exc
    if not isinstance(payload, dict) or not payload:
        record_overlay_failure("overlay 内容为空")
        raise TarkovOverlayError("overlay 内容为空")
    source = f"{REPO_TARKOV_OVERLAY}/{OVERLAY_REL}"
    _record_overlay_success(source, None)
    logger.info("tarkov overlay read ok (%s)", json_api_prefix())
    return payload, None


def _record_overlay_success(url: str, upstream_at: str | None) -> None:
    _last_success.clear()
    _last_success.update(
        {
            "url": url,
            "at": timeutil.now().isoformat(),
            "upstream_at": upstream_at,
            "error": None,
        }
    )


def record_overlay_failure(error: str) -> None:
    """同步失败时记一笔：overlay_status 里能看出「源挂了、用的是上一份」。"""
    _last_success["error"] = error


def overlay_status(db: Session) -> dict[str, Any]:
    """overlay 新鲜度：最近一次成功（进程内）+ 库里的 synced_at；给同步结果与排障用。"""
    last = dict(_last_success)
    row = None
    try:
        row = upstream_svc.load_raw_row(db, OVERLAY_RESOURCE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tarkov overlay header unavailable: %s", exc)
    synced_at = row.synced_at.isoformat() if row is not None and row.synced_at else None
    age_sec: int | None = None
    if row is not None and row.synced_at:
        # synced_at 存的是北京墙钟（无时区）：按北京解释，不能当成 UTC，否则年龄少算 8 小时。
        age_sec = int((timeutil.now() - timeutil.ensure(row.synced_at)).total_seconds())
    return {
        "url": last.get("url") or "",
        "last_success_at": last.get("at") or synced_at,
        "synced_at": synced_at,
        "upstream_at": last.get("upstream_at") or upstream_svc.notes_upstream_at(
            row.note if row is not None else None
        ),
        "age_seconds": age_sec,
        "stale": bool(age_sec is not None and age_sec > OVERLAY_STALE_AFTER_SEC),
        "error": last.get("error"),
    }


def persist_overlay(
    db: Session,
    payload: dict[str, Any],
    *,
    upstream_at: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    default_source = f"{REPO_TARKOV_OVERLAY}/{OVERLAY_REL}"
    origin = (source_url or _last_success.get("url") or default_source).strip()
    return upstream_svc.persist_raw(
        db,
        OVERLAY_RESOURCE,
        payload,
        source=SOURCE_OVERLAY,
        note=f"{SOURCE_OVERLAY} {origin}",
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
    """overlay raw 的 synced_at；一次请求里各栏目算 parse key / ETag 共用一次查询。"""
    memo = upstream_svc.session_memo(db)
    memo_key = ("overlay_token", parse_game_mode())
    if memo is not None and memo_key in memo:
        return memo[memo_key]
    try:
        row = upstream_svc.load_raw_row(db, OVERLAY_RESOURCE)
    except Exception as exc:
        logger.warning("tarkov overlay cache token unavailable: %s", exc)
        return ""
    token = row.synced_at.isoformat() if row is not None and row.synced_at else ""
    if memo is not None:
        memo[memo_key] = token
    return token


def parsed_cache_key(
    db: Session,
    resource_synced: str | None,
    *,
    resource: str | None = None,
) -> str:
    """解析缓存键：主文件版本 + overlay 版本 +（给了 resource 时）locale 版本。

    只翻中文不改结构的上游更新不会动主文件字节（persist_raw 会保留 synced_at），
    只有 locale 行会变；不带它就得重启才看得到新译文。
    """
    parts = [resource_synced or "", overlay_cache_token(db), OVERLAY_PARSE_REV]
    if resource:
        parts.append(upstream_svc.locale_synced(db, resource))
    return cache_key(*parts)


def apply_loaded_overlay(
    db: Session,
    resource: str,
    payload: dict[str, Any],
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    return apply_overlay(resource, payload, load_overlay(db), game_mode=game_mode)
