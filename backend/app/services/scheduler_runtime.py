"""APScheduler 任务注册 / 热重载（供 lifespan 与管理端共用）。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.timeutil import BEIJING
from app.services.arknights_box_compare import (
    box_sync_job_wrapper as arknights_box_sync_job_wrapper,
)
from app.services.arknights_catalog import (
    catalog_sync_job_wrapper as arknights_catalog_sync_job_wrapper,
)
from app.services.exilium_checkin import checkin_job_wrapper as exilium_checkin_job_wrapper
from app.services.integrations_config import get_steam_api_key
from app.services.job_runs_prune import prune_job_wrapper
from app.services.kujiequ_checkin import checkin_job_wrapper as kujiequ_checkin_job_wrapper
from app.services.minecraft_presence import poll_job_wrapper as minecraft_presence_job
from app.services.minecraft_perf import (
    SAMPLE_INTERVAL_SEC as MINECRAFT_PERF_INTERVAL_SEC,
)
from app.services.minecraft_perf import poll_job_wrapper as minecraft_rcon_perf_job
from app.services.platform_features import JOB_FEATURE_IDS, is_feature_enabled
from app.services.scheduler_config import JOB_IDS, load_scheduler_config
from app.services.skland_checkin import checkin_job_wrapper as skland_checkin_job_wrapper
from app.services.steam_poller import poll_job_wrapper
from app.services.taygedo_checkin import checkin_job_wrapper as taygedo_checkin_job_wrapper
from app.services.tarkov_bosses import (
    bosses_sync_job_wrapper as tarkov_bosses_sync_job_wrapper,
)
from app.services.tarkov_guides import (
    guides_sync_job_wrapper as tarkov_guides_sync_job_wrapper,
)
from app.services.tarkov_items import items_sync_job_wrapper as tarkov_items_sync_job_wrapper
from app.services.tarkov_tasks import tasks_sync_job_wrapper as tarkov_tasks_sync_job_wrapper
from app.services.tarkov_traders import (
    traders_sync_job_wrapper as tarkov_traders_sync_job_wrapper,
)

logger = logging.getLogger("zhange.scheduler")

_SCHEDULER_LOCK = threading.Lock()
_MANUAL_TRIGGER_LOCKS: dict[str, threading.Lock] = {
    job_id: threading.Lock() for job_id in JOB_IDS
}

APP_EXECUTOR_ID = "app"
APP_EXECUTOR_NAME = "战鸽应用"

CHECKIN_JOB_IDS = (
    "skland_checkin",
    "taygedo_checkin",
    "exilium_checkin",
    "kujiequ_checkin",
)

CHECKIN_DUE_HANDLERS: dict[str, Callable[[], None]] = {
    "skland_checkin": lambda: skland_checkin_job_wrapper(due_only=True),
    "taygedo_checkin": lambda: taygedo_checkin_job_wrapper(due_only=True),
    "exilium_checkin": lambda: exilium_checkin_job_wrapper(due_only=True),
    "kujiequ_checkin": lambda: kujiequ_checkin_job_wrapper(due_only=True),
}

CHECKIN_MANUAL_HANDLERS: dict[str, Callable[..., None]] = {
    "skland_checkin": skland_checkin_job_wrapper,
    "taygedo_checkin": taygedo_checkin_job_wrapper,
    "exilium_checkin": exilium_checkin_job_wrapper,
    "kujiequ_checkin": kujiequ_checkin_job_wrapper,
}

SYSTEM_CRON_HANDLERS: dict[str, Callable[[], None]] = {
    "arknights_box_sync": arknights_box_sync_job_wrapper,
    "arknights_catalog_sync": arknights_catalog_sync_job_wrapper,
    "tarkov_items_sync": tarkov_items_sync_job_wrapper,
    "tarkov_tasks_sync": tarkov_tasks_sync_job_wrapper,
    "tarkov_traders_sync": tarkov_traders_sync_job_wrapper,
    "tarkov_bosses_sync": tarkov_bosses_sync_job_wrapper,
    "tarkov_guides_sync": tarkov_guides_sync_job_wrapper,
    "job_runs_prune": prune_job_wrapper,
}

CRON_JOB_HANDLERS = {
    **CHECKIN_DUE_HANDLERS,
    **SYSTEM_CRON_HANDLERS,
}


def _job_feature_allowed(db: Session, job_id: str) -> bool:
    feature_id = JOB_FEATURE_IDS.get(job_id)
    if feature_id is None:
        return True
    return is_feature_enabled(db, feature_id)


def resolve_job_callable(
    job_id: str,
    db: Session,
    *,
    member_id: int | None = None,
) -> Callable[[], None]:
    """解析手动触发入口（签到默认跑全部 auto 用户，可指定 member_id）。"""
    if not _job_feature_allowed(db, job_id):
        raise RuntimeError("该任务所属功能未启用")
    if job_id == "steam_presence":
        return poll_job_wrapper
    if job_id == "minecraft_presence":
        return minecraft_presence_job
    if job_id in CHECKIN_MANUAL_HANDLERS:
        handler = CHECKIN_MANUAL_HANDLERS[job_id]

        def _run() -> None:
            handler(due_only=False, member_id=member_id)

        return _run
    handler = SYSTEM_CRON_HANDLERS.get(job_id)
    if handler is None:
        raise KeyError(job_id)
    return handler


def try_acquire_manual_trigger(job_id: str) -> bool:
    lock = _MANUAL_TRIGGER_LOCKS.get(job_id)
    if lock is None:
        return False
    return lock.acquire(blocking=False)


def release_manual_trigger(job_id: str) -> None:
    lock = _MANUAL_TRIGGER_LOCKS.get(job_id)
    if lock is None:
        return
    try:
        lock.release()
    except RuntimeError:
        pass


def _remove_job(scheduler: BackgroundScheduler, job_id: str) -> None:
    try:
        scheduler.remove_job(job_id)
    except Exception:  # noqa: BLE001 — job 可能不存在
        pass


def register_scheduler_jobs(
    scheduler: BackgroundScheduler,
    db: Session,
    *,
    run_steam_once: bool = False,
) -> bool:
    """按 DB/env 配置与平台功能开关注册任务。返回是否至少注册了一个任务。"""
    cfg = load_scheduler_config(db)
    steam_key = get_steam_api_key(db)
    started = False

    with _SCHEDULER_LOCK:
        for job_id in JOB_IDS:
            _remove_job(scheduler, job_id)

        steam_cfg = cfg.get("steam_presence") or {}
        interval = max(1, int(steam_cfg.get("interval_minutes") or 3))

        # 是否注册只认平台功能开关；interval/cron 时刻仍读 scheduler_jobs
        if _job_feature_allowed(db, "steam_presence") and steam_key:
            scheduler.add_job(
                poll_job_wrapper,
                "interval",
                minutes=interval,
                id="steam_presence",
                replace_existing=True,
                max_instances=1,
            )
            started = True
            if run_steam_once:
                poll_job_wrapper()

        mc_cfg = cfg.get("minecraft_presence") or {}
        mc_interval = max(1, int(mc_cfg.get("interval_minutes") or 1))
        if _job_feature_allowed(db, "minecraft_presence"):
            scheduler.add_job(
                minecraft_presence_job,
                "interval",
                minutes=mc_interval,
                id="minecraft_presence",
                replace_existing=True,
                max_instances=1,
            )
            started = True

        # 平台签到：功能开启时每分钟巡检（用户 auto_checkin + HH:MM）
        for job_id, func in CHECKIN_DUE_HANDLERS.items():
            if not _job_feature_allowed(db, job_id):
                continue
            scheduler.add_job(
                func,
                "interval",
                minutes=1,
                id=job_id,
                replace_existing=True,
                max_instances=1,
            )
            started = True

        for job_id, func in SYSTEM_CRON_HANDLERS.items():
            if not _job_feature_allowed(db, job_id):
                continue
            job_cfg = cfg.get(job_id) or {}
            # 维护任务默认可跑；scheduler_jobs.job_runs_prune.enabled=false 可关闭
            if job_id == "job_runs_prune" and job_cfg.get("enabled") is False:
                continue
            hour = max(0, min(23, int(job_cfg.get("hour", 0))))
            minute = max(0, min(59, int(job_cfg.get("minute", 0))))
            scheduler.add_job(
                func,
                "cron",
                hour=hour,
                minute=minute,
                timezone=BEIJING,
                id=job_id,
                replace_existing=True,
                max_instances=1,
            )
            started = True

        _remove_job(scheduler, "minecraft_rcon_perf")
        if is_feature_enabled(db, "guides.minecraft"):
            scheduler.add_job(
                minecraft_rcon_perf_job,
                "interval",
                seconds=MINECRAFT_PERF_INTERVAL_SEC,
                id="minecraft_rcon_perf",
                replace_existing=True,
                max_instances=1,
            )
            started = True

        if started and not scheduler.running:

            def _start_scheduler() -> None:
                if not scheduler.running:
                    scheduler.start()

            threading.Thread(
                target=_start_scheduler,
                name="apscheduler-start",
                daemon=True,
            ).start()

    return started
