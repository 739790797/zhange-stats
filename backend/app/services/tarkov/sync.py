"""塔科夫攻略全量回源：整站 dump 按文件落 raw，再派生弹药/枪械并校验栏目。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.services.tarkov import bosses as bosses_svc
from app.services.tarkov import guides as guides_svc
from app.services.tarkov import items as items_svc
from app.services.tarkov import key_packs as key_packs_svc
from app.services.tarkov import overlay as overlay_svc
from app.services.tarkov import tasks as tasks_svc
from app.services.tarkov import traders as traders_svc
from app.services.tarkov import upstream as upstream_svc
from app.services.tarkov.ammo import SOURCE_JSON_API
from app.services.tarkov.game_mode import (
    game_mode_scope,
    json_api_prefix,
    parse_game_mode,
    sync_modes,
)

logger = logging.getLogger(__name__)

FULL_SYNC_JOB_KEY = "tarkov_full_sync"


class TarkovFullSyncError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _domain_row(
    domain_id: str,
    *,
    ok: bool,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": domain_id,
        "ok": ok,
        "error": error,
        "mode": parse_game_mode(),
    }
    if result:
        row["source"] = result.get("source")
        row["synced_at"] = result.get("synced_at")
        row["upstream_at"] = result.get("upstream_at")
    else:
        row["source"] = None
        row["synced_at"] = None
        row["upstream_at"] = None
    return row


def _json_note(resource: str) -> str:
    return f"json.tarkov.dev/{json_api_prefix()}/{resource}"


def _dump_result(resource: str, **counts: Any) -> dict[str, Any]:
    out = {
        "source": SOURCE_JSON_API,
        "synced_at": now_naive().isoformat(),
        "note": _json_note(resource),
    }
    out.update(counts)
    return out


def _apply_items(db: Session, dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    items = dump.get("items")
    if not isinstance(items, dict) or not items:
        raise items_svc.TarkovItemsError("dump 缺少 items")
    return items_svc.rebuild_from_raw(db)


def _apply_tasks(_db: Session, dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = dump.get("tasks")
    if not isinstance(payload, dict) or not payload:
        raise tasks_svc.TarkovTasksError("dump 缺少 tasks")
    tasks = tasks_svc._tasks_map(payload)
    if not tasks:
        raise tasks_svc.TarkovTasksError("dump tasks 未解析到任务")
    return _dump_result("tasks", task_count=len(tasks))


def _apply_maps(_db: Session, dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = dump.get("maps")
    if not isinstance(payload, dict) or not payload:
        raise bosses_svc.TarkovBossesError("dump 缺少 maps")
    maps = bosses_svc._maps_blob(payload)
    mobs = bosses_svc._mobs_blob(payload)
    if not maps or not mobs:
        raise bosses_svc.TarkovBossesError("dump maps 未解析到地图 / BOSS")
    return _dump_result("maps", boss_count=len(bosses_svc.parse_boss_rows(payload)))


def _apply_guides(_db: Session, dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    hideout_payload = dump.get("hideout")
    barters_payload = dump.get("barters")
    crafts_payload = dump.get("crafts")
    if not isinstance(hideout_payload, dict) or not hideout_payload:
        raise guides_svc.TarkovGuidesError("dump 缺少 hideout")
    if not isinstance(barters_payload, dict):
        raise guides_svc.TarkovGuidesError("dump barters 格式无效")
    if not isinstance(crafts_payload, dict):
        raise guides_svc.TarkovGuidesError("dump crafts 格式无效")
    envelope = guides_svc.assemble_guides_envelope(
        hideout_payload,
        barters_payload=barters_payload,
        crafts_payload=crafts_payload,
        locale=upstream_svc.locale_data(dump, "hideout"),
    )
    if not envelope.get("hideout"):
        raise guides_svc.TarkovGuidesError("dump hideout 为空")
    stations = guides_svc.parse_hideout_stations(envelope)
    if not stations:
        raise guides_svc.TarkovGuidesError("dump hideout 未解析到藏身处")
    return _dump_result(
        "hideout",
        station_count=len(stations),
        barter_count=len(guides_svc.parse_barters(envelope)),
        craft_count=len(guides_svc.parse_crafts(envelope)),
    )


def _apply_traders(_db: Session, dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    traders_payload = dump.get("traders")
    items = dump.get("items")
    if not isinstance(traders_payload, dict) or not traders_payload:
        raise traders_svc.TarkovTradersError("dump 缺少 traders")
    if not isinstance(items, dict) or not items:
        raise traders_svc.TarkovTradersError("dump 缺少 items，无法解析商人报价")
    traders = traders_svc._traders_map(traders_payload)
    if not traders:
        raise traders_svc.TarkovTradersError("dump traders 未解析到商人")
    return _dump_result("traders", trader_count=len(traders))


def _seed_locks(dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = dump.get("maps")
    if not isinstance(payload, dict) or not payload:
        raise key_packs_svc.TarkovKeyPacksError("dump 缺少 maps，无法刷新门锁")
    maps = key_packs_svc.parse_json_maps_locks(payload)
    if not key_packs_svc.maps_have_lock_data(maps):
        raise key_packs_svc.TarkovKeyPacksError("dump maps 没有门锁")
    now = time.time()
    key_packs_svc._lock_cache[key_packs_svc._cache_key(parse_game_mode())] = {
        "at": now,
        "maps": maps,
        "source": key_packs_svc.SOURCE_JSON,
    }
    return {
        "source": key_packs_svc.SOURCE_JSON,
        "synced_at": now_naive().isoformat(),
        "map_count": len(maps),
    }


def _apply_extras(db: Session, dump: dict[str, dict[str, Any]]) -> dict[str, Any]:
    data = upstream_svc.extras_from_site_dump(dump)
    return upstream_svc.persist_raw(
        db,
        upstream_svc.EXTRAS_RESOURCE,
        data,
        source=SOURCE_JSON_API,
        note=f"json.tarkov.dev/{json_api_prefix()} extras",
    )


_APPLY_STEPS: tuple[tuple[str, Any, type[Exception]], ...] = (
    ("items", _apply_items, items_svc.TarkovItemsError),
    ("tasks", _apply_tasks, tasks_svc.TarkovTasksError),
    ("maps", _apply_maps, bosses_svc.TarkovBossesError),
    ("guides", _apply_guides, guides_svc.TarkovGuidesError),
    ("traders", _apply_traders, traders_svc.TarkovTradersError),
    ("locks", lambda db, dump: _seed_locks(dump), key_packs_svc.TarkovKeyPacksError),
)


def _sync_current_mode(db: Session, *, lang: str = "zh") -> list[dict[str, Any]]:
    mode = parse_game_mode()
    logger.info("tarkov full site dump (%s)", mode)
    domains: list[dict[str, Any]] = []
    try:
        dump, upstream_times = upstream_svc.download_site_json(lang=lang)
        domains.extend(
            upstream_svc.persist_site_json(
                db, dump, lang=lang, upstream_times=upstream_times
            )
        )
    except upstream_svc.TarkovUpstreamError as exc:
        logger.warning("tarkov site dump failed (%s): %s", mode, exc)
        return [
            _domain_row("dump", ok=False, error=str(exc)),
        ]

    try:
        overlay = overlay_svc.sync_overlay(db)
        domains.append(_domain_row("overlay", ok=True, result=overlay))
    except overlay_svc.TarkovOverlayError as exc:
        logger.warning("tarkov overlay dump failed (%s): %s", mode, exc)
        domains.append(_domain_row("overlay", ok=False, error=str(exc)))

    for domain_id, fn, error_cls in _APPLY_STEPS:
        try:
            result = fn(db, dump)
            domains.append(_domain_row(domain_id, ok=True, result=result))
        except error_cls as exc:
            logger.warning("tarkov full sync %s failed: %s", domain_id, exc)
            domains.append(_domain_row(domain_id, ok=False, error=str(exc)))

    try:
        extras = _apply_extras(db, dump)
        domains.append(_domain_row("extras", ok=True, result=extras))
    except upstream_svc.TarkovUpstreamError as exc:
        logger.warning("tarkov extras dump failed: %s", exc)
        domains.append(_domain_row("extras", ok=False, error=str(exc)))

    return domains


def sync_all_from_upstream(
    db: Session,
    *,
    game_mode: str | None = None,
    lang: str = "zh",
) -> dict[str, Any]:
    """拉齐 json.tarkov.dev 全文件；raw 只写一次，再派生弹药/枪械。 extras 从 dump 投影。"""
    domains: list[dict[str, Any]] = []
    for mode in sync_modes(game_mode):
        with game_mode_scope(mode):
            domains.extend(_sync_current_mode(db, lang=lang))

    ok_count = sum(1 for row in domains if row["ok"])
    failed_count = len(domains) - ok_count
    if ok_count == 0:
        detail = "；".join(
            f"{row['id']}: {row.get('error') or '失败'}" for row in domains
        )
        raise TarkovFullSyncError(f"全量同步失败：{detail}")
    return {
        "ok_count": ok_count,
        "failed_count": failed_count,
        "domains": domains,
        "message": "ok" if failed_count == 0 else "partial",
    }


def full_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    job = JobRun(job_key=FULL_SYNC_JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        result = sync_all_from_upstream(db)
        job.status = "ok" if int(result.get("failed_count") or 0) == 0 else "error"
        job.message = json.dumps(
            {
                "ok_count": result.get("ok_count"),
                "failed_count": result.get("failed_count"),
                "domains": [
                    {
                        "id": row.get("id"),
                        "ok": row.get("ok"),
                        "error": row.get("error"),
                        "source": row.get("source"),
                        "mode": row.get("mode"),
                        "synced_at": row.get("synced_at"),
                        "upstream_at": row.get("upstream_at"),
                    }
                    for row in result.get("domains") or []
                ],
            },
            ensure_ascii=False,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov full sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
