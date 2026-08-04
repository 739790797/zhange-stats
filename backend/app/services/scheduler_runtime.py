"""APScheduler 任务注册 / 热重载（供 lifespan 与管理端共用）。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.local_dev_hooks import import_steam_fake
from app.core.timeutil import BEIJING
from app.services.arknights_box_compare import (
    box_sync_job_wrapper as arknights_box_sync_job_wrapper,
)
from app.services.dev_config import is_steam_fake_poll
from app.services.exilium_checkin import checkin_job_wrapper as exilium_checkin_job_wrapper
from app.services.integrations_config import get_steam_api_key
from app.services.scheduler_config import JOB_IDS, load_scheduler_config
from app.services.skland_checkin import checkin_job_wrapper as skland_checkin_job_wrapper
from app.services.steam_poller import poll_job_wrapper
from app.services.taygedo_checkin import checkin_job_wrapper as taygedo_checkin_job_wrapper

logger = logging.getLogger("zhange.scheduler")

_SCHEDULER_LOCK = threading.Lock()


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
    """按 DB/env 配置注册任务。返回是否至少注册了一个任务。"""
    cfg = load_scheduler_config(db)
    steam_key = get_steam_api_key(db)
    fake_poll = is_steam_fake_poll(db)
    started = False

    with _SCHEDULER_LOCK:
        # 先清掉已知任务，再按配置重建
        for job_id in JOB_IDS:
            _remove_job(scheduler, job_id)

        steam_fake = import_steam_fake() if fake_poll else None
        steam_cfg = cfg.get("steam_presence") or {}
        interval = max(1, int(steam_cfg.get("interval_minutes") or 3))

        if fake_poll and steam_fake is not None:
            scheduler.add_job(
                steam_fake.fake_poll_job_wrapper,
                "interval",
                minutes=interval,
                id="steam_presence",
                replace_existing=True,
                max_instances=1,
            )
            started = True
            if run_steam_once:
                steam_fake.fake_poll_job_wrapper()
        elif fake_poll and steam_fake is None:
            logger.warning(
                "已开启本地假监控但未找到 local_dev.steam_fake，已跳过假监控"
            )
        elif steam_cfg.get("enabled") and steam_key:
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

        cron_jobs: list[tuple[str, Any]] = [
            ("skland_checkin", skland_checkin_job_wrapper),
            ("arknights_box_sync", arknights_box_sync_job_wrapper),
            ("taygedo_checkin", taygedo_checkin_job_wrapper),
            ("exilium_checkin", exilium_checkin_job_wrapper),
        ]
        for job_id, func in cron_jobs:
            job_cfg = cfg.get(job_id) or {}
            if not job_cfg.get("enabled"):
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


def ensure_local_fake_data_if_needed(db: Session) -> None:
    if not is_steam_fake_poll(db):
        return
    steam_fake = import_steam_fake()
    if steam_fake is None:
        return
    steam_fake.ensure_local_fake_data(db)
