"""塔科夫攻略全量回源：整站 dump 按文件落 raw，再派生弹药/枪械并校验栏目。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
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
        "status": "ok" if ok else "error",
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

APPLY_DOMAIN_IDS: tuple[str, ...] = (
    "overlay",
    *(step[0] for step in _APPLY_STEPS),
    "extras",
)

ProgressFn = Callable[[str, dict[str, Any]], None]

_DONE_STATUSES = frozenset({"ok", "error", "skipped", "downloaded", "persisting"})
_FLUSH_PHASES = frozenset(
    {"start", "persist", "apply", "overlay", "done", "error"}
)


def format_full_sync_message(phase: str, **kwargs: Any) -> str:
    file = str(kwargs.get("file") or "")
    index = kwargs.get("index")
    total = kwargs.get("total")
    if phase == "download":
        if index and total:
            return f"正在下载 {file or 'dump'}（{index}/{total}）"
        return f"正在下载 {file or 'dump'}"
    if phase == "persist":
        return f"正在写入 {file or 'dump'}…"
    if phase == "overlay":
        return "正在下载 overlay…"
    if phase == "apply":
        return f"正在投影 {file or '栏目'}…"
    if phase == "done":
        return "全量更新完成"
    if phase == "error":
        return str(kwargs.get("error") or "全量更新失败")
    return "正在全量更新…"


def planned_full_sync_domains(
    modes: Sequence[str], *, lang: str = "zh"
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mode in modes:
        for _resource, _res_lang, domain_id in upstream_svc.site_dump_specs(lang=lang):
            rows.append(_pending_row(domain_id, mode))
        for domain_id in APPLY_DOMAIN_IDS:
            rows.append(_pending_row(domain_id, mode))
    return rows


def _pending_row(domain_id: str, mode: str) -> dict[str, Any]:
    return {
        "id": domain_id,
        "ok": False,
        "status": "pending",
        "error": None,
        "mode": mode,
        "source": None,
        "synced_at": None,
        "upstream_at": None,
    }


def _progress_percent(
    domains: Sequence[dict[str, Any]], *, byte_frac: float = 0.0
) -> int:
    total = len(domains)
    if total <= 0:
        return 0
    done = sum(1 for row in domains if row.get("status") in _DONE_STATUSES)
    running = any(
        row.get("status") in {"downloading", "applying"} for row in domains
    )
    frac = max(0.0, min(1.0, byte_frac)) if running else 0.0
    return max(0, min(99, int(100 * (done + frac) / total)))


class _SyncProgress:
    def __init__(self, domains: list[dict[str, Any]], emit: ProgressFn | None):
        self.domains = domains
        self._emit = emit
        self.mode = ""

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def _row(self, domain_id: str) -> dict[str, Any] | None:
        for row in self.domains:
            if row.get("id") == domain_id and row.get("mode") == self.mode:
                return row
        return None

    def patch(self, domain_id: str, **fields: Any) -> dict[str, Any] | None:
        row = self._row(domain_id)
        if row is None:
            return None
        row.update(fields)
        return row

    def fail_dumps(self, error: str) -> None:
        for row in self.domains:
            if row.get("mode") != self.mode:
                continue
            ident = str(row.get("id") or "")
            if ident.startswith("dump:") and row.get("status") not in {"ok", "error"}:
                row["status"] = "error"
                row["ok"] = False
                row["error"] = error
            elif row.get("status") == "pending":
                row["status"] = "skipped"
                row["ok"] = False
                row["error"] = "dump 未完成"

    def emit(self, phase: str, **kwargs: Any) -> None:
        if self._emit is None:
            return
        byte_frac = 0.0
        bytes_n = kwargs.get("bytes")
        total_bytes = kwargs.get("total_bytes")
        try:
            if total_bytes and bytes_n is not None and float(total_bytes) > 0:
                byte_frac = float(bytes_n) / float(total_bytes)
        except (TypeError, ValueError):
            byte_frac = 0.0
        percent = 100 if phase == "done" else _progress_percent(
            self.domains, byte_frac=byte_frac
        )
        stats: dict[str, Any] = {
            "phase": phase,
            "percent": percent,
            "domains": [dict(row) for row in self.domains],
        }
        for key in ("file", "bytes", "total_bytes", "files_done", "files_total"):
            if kwargs.get(key) is not None:
                stats[key] = kwargs[key]
        self._emit(format_full_sync_message(phase, **kwargs), stats)


def _sync_current_mode(
    db: Session,
    *,
    lang: str = "zh",
    tracker: _SyncProgress | None = None,
) -> list[dict[str, Any]]:
    mode = parse_game_mode()
    logger.info("tarkov full site dump (%s)", mode)
    if tracker is not None:
        tracker.set_mode(mode)
    domains: list[dict[str, Any]] = []
    dump_specs = upstream_svc.site_dump_specs(lang=lang)
    dump_total = len(dump_specs)

    def on_download(event: dict[str, Any]) -> None:
        if tracker is None:
            return
        domain_id = str(event.get("domain_id") or "")
        error = event.get("error")
        done = bool(event.get("done"))
        index = int(event.get("index") or 0)
        total = int(event.get("total") or dump_total)
        if error:
            tracker.patch(
                domain_id, status="error", ok=False, error=str(error)
            )
        elif done:
            tracker.patch(domain_id, status="downloaded", ok=False, error=None)
            row = tracker._row(domain_id)
            if row is not None:
                row.pop("bytes", None)
                row.pop("total_bytes", None)
        else:
            tracker.patch(
                domain_id,
                status="downloading",
                ok=False,
                bytes=event.get("bytes") or 0,
                total_bytes=event.get("total_bytes"),
            )
        files_done = index if done else max(0, index - 1)
        tracker.emit(
            "download",
            file=event.get("file"),
            index=index,
            total=total,
            bytes=event.get("bytes"),
            total_bytes=event.get("total_bytes"),
            files_done=files_done,
            files_total=total,
        )

    def on_persist(event: dict[str, Any]) -> None:
        if tracker is None:
            return
        domain_id = str(event.get("domain_id") or "")
        tracker.patch(domain_id, status="persisting", ok=False)
        tracker.emit(
            "persist",
            file=event.get("file"),
            index=event.get("index"),
            total=event.get("total"),
            files_done=max(0, int(event.get("index") or 1) - 1),
            files_total=event.get("total") or dump_total,
        )

    try:
        if tracker is not None:
            first = dump_specs[0][0] if dump_specs else "dump"
            tracker.emit(
                "download",
                file=first,
                index=1,
                total=dump_total,
                files_done=0,
                files_total=dump_total,
            )
        dump, upstream_times = upstream_svc.download_site_json(
            lang=lang, on_progress=on_download
        )
        persist_rows = upstream_svc.persist_site_json(
            db,
            dump,
            lang=lang,
            upstream_times=upstream_times,
            on_progress=on_persist,
        )
        domains.extend(persist_rows)
        if tracker is not None:
            for row in persist_rows:
                tracker.patch(
                    str(row.get("id") or ""),
                    status="ok" if row.get("ok") else "error",
                    ok=bool(row.get("ok")),
                    error=row.get("error"),
                    source=row.get("source"),
                    synced_at=row.get("synced_at"),
                    upstream_at=row.get("upstream_at"),
                )
    except upstream_svc.TarkovUpstreamError as exc:
        logger.warning("tarkov site dump failed (%s): %s", mode, exc)
        if tracker is not None:
            tracker.fail_dumps(str(exc))
            tracker.emit("error", error=str(exc))
        return [
            _domain_row("dump", ok=False, error=str(exc)),
        ]

    try:
        if tracker is not None:
            tracker.patch("overlay", status="downloading", ok=False)
            tracker.emit("overlay", file="overlay")

        def overlay_bytes(n: int, total: int | None) -> None:
            if tracker is None:
                return
            tracker.patch(
                "overlay",
                status="downloading",
                ok=False,
                bytes=n,
                total_bytes=total,
            )
            tracker.emit("overlay", file="overlay", bytes=n, total_bytes=total)

        overlay = overlay_svc.sync_overlay(db, on_bytes=overlay_bytes)
        domains.append(_domain_row("overlay", ok=True, result=overlay))
        if tracker is not None:
            tracker.patch(
                "overlay",
                status="ok",
                ok=True,
                error=None,
                source=overlay.get("source"),
                synced_at=overlay.get("synced_at"),
                upstream_at=overlay.get("upstream_at"),
            )
    except overlay_svc.TarkovOverlayError as exc:
        logger.warning("tarkov overlay dump failed (%s): %s", mode, exc)
        domains.append(_domain_row("overlay", ok=False, error=str(exc)))
        if tracker is not None:
            tracker.patch("overlay", status="error", ok=False, error=str(exc))

    for domain_id, fn, error_cls in _APPLY_STEPS:
        if tracker is not None:
            tracker.patch(domain_id, status="applying", ok=False)
            tracker.emit("apply", file=domain_id)
        try:
            result = fn(db, dump)
            domains.append(_domain_row(domain_id, ok=True, result=result))
            if tracker is not None:
                tracker.patch(
                    domain_id,
                    status="ok",
                    ok=True,
                    error=None,
                    source=result.get("source"),
                    synced_at=result.get("synced_at"),
                    upstream_at=result.get("upstream_at"),
                )
        except error_cls as exc:
            logger.warning("tarkov full sync %s failed: %s", domain_id, exc)
            domains.append(_domain_row(domain_id, ok=False, error=str(exc)))
            if tracker is not None:
                tracker.patch(domain_id, status="error", ok=False, error=str(exc))

    if tracker is not None:
        tracker.patch("extras", status="applying", ok=False)
        tracker.emit("apply", file="extras")
    try:
        extras = _apply_extras(db, dump)
        domains.append(_domain_row("extras", ok=True, result=extras))
        if tracker is not None:
            tracker.patch(
                "extras",
                status="ok",
                ok=True,
                error=None,
                source=extras.get("source"),
                synced_at=extras.get("synced_at"),
                upstream_at=extras.get("upstream_at"),
            )
    except upstream_svc.TarkovUpstreamError as exc:
        logger.warning("tarkov extras dump failed: %s", exc)
        domains.append(_domain_row("extras", ok=False, error=str(exc)))
        if tracker is not None:
            tracker.patch("extras", status="error", ok=False, error=str(exc))

    return domains


def sync_all_from_upstream(
    db: Session,
    *,
    game_mode: str | None = None,
    lang: str = "zh",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """拉齐 json.tarkov.dev 全文件；raw 只写一次，再派生弹药/枪械。 extras 从 dump 投影。"""
    modes = sync_modes(game_mode)
    tracker = _SyncProgress(planned_full_sync_domains(modes, lang=lang), progress)
    tracker.emit("start")
    domains: list[dict[str, Any]] = []
    for mode in modes:
        with game_mode_scope(mode):
            domains.extend(_sync_current_mode(db, lang=lang, tracker=tracker))

    ok_count = sum(1 for row in domains if row["ok"])
    failed_count = len(domains) - ok_count
    if ok_count == 0:
        detail = "；".join(
            f"{row['id']}: {row.get('error') or '失败'}" for row in domains
        )
        raise TarkovFullSyncError(f"全量同步失败：{detail}")
    tracker.emit("done")
    return {
        "ok_count": ok_count,
        "failed_count": failed_count,
        "domains": domains,
        "message": "ok" if failed_count == 0 else "partial",
    }


def _write_job_run(
    run_id: int,
    *,
    status: str | None = None,
    message: str | None = None,
    stats: dict[str, Any] | None = None,
    finished: bool = False,
) -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    try:
        row = db.get(JobRun, run_id)
        if row is None:
            return
        if message is not None:
            row.message = message
        if stats is not None:
            row.stats = stats
        if status is not None:
            row.status = status
        if finished:
            row.finished_at = now_naive()
        db.commit()
    except Exception:
        logger.exception("tarkov full sync job_run write failed")
        db.rollback()
    finally:
        db.close()


def _domain_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "ok": row.get("ok"),
        "status": row.get("status") or ("ok" if row.get("ok") else "error"),
        "error": row.get("error"),
        "source": row.get("source"),
        "mode": row.get("mode"),
        "synced_at": row.get("synced_at"),
        "upstream_at": row.get("upstream_at"),
    }


def full_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal
    from app.models.job_run import JobRun

    db = SessionLocal()
    run = JobRun(
        job_key=FULL_SYNC_JOB_KEY,
        status="running",
        message=format_full_sync_message("start"),
        stats={
            "phase": "start",
            "percent": 0,
            "domains": planned_full_sync_domains(sync_modes(), lang="zh"),
        },
    )
    db.add(run)
    db.commit()
    run_id = int(run.id)
    db.close()

    last_at = 0.0

    def progress(message: str, stats: dict[str, Any]) -> None:
        nonlocal last_at
        now = time.monotonic()
        phase = str(stats.get("phase") or "")
        force = phase in _FLUSH_PHASES
        if not force and now - last_at < 0.45:
            return
        last_at = now
        _write_job_run(run_id, message=message, stats=stats)

    db = SessionLocal()
    try:
        result = sync_all_from_upstream(db, progress=progress)
        failed = int(result.get("failed_count") or 0)
        payload = {
            "ok_count": result.get("ok_count"),
            "failed_count": failed,
            "domains": [
                _domain_payload(row) for row in result.get("domains") or []
            ],
        }
        _write_job_run(
            run_id,
            status="ok" if failed == 0 else "error",
            message=json.dumps(payload, ensure_ascii=False),
            stats={
                "phase": "done" if failed == 0 else "error",
                "percent": 100,
                "domains": payload["domains"],
            },
            finished=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("tarkov full sync job failed")
        _write_job_run(
            run_id,
            status="error",
            message=str(exc),
            stats={"phase": "error", "percent": 0},
            finished=True,
        )
    finally:
        db.close()
