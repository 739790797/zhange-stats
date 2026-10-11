"""数据库就绪后的启动步骤。lifespan 与安装向导完成后共用，避免向导后要等重启才跑调度。"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger("zhange.startup")

_texteller_lock = threading.Lock()
_texteller_started = False


def _run_security_checks(db: Any, *, enforce: bool) -> None:
    from app.services.security_bootstrap import (
        check_admin_password_health,
        check_email_code_log_policy,
    )

    logger.info("startup step 5/9: email code log policy")
    logger.info("startup step 6/9: admin password health")
    if enforce:
        check_email_code_log_policy()
        check_admin_password_health(db)
        return
    try:
        check_email_code_log_policy()
        check_admin_password_health(db)
    except Exception:  # noqa: BLE001
        logger.warning("security bootstrap check failed; enforced on next restart", exc_info=True)


def run_post_database_startup(
    scheduler: Any,
    *,
    run_steam_once: bool = True,
    enforce_security_checks: bool = True,
) -> None:
    """迁移之后：时间存储、种子、安全检查、成员同步、附件登记、回收中断任务、注册调度。"""
    from app.core.beijing_time_migrate import ensure_beijing_time_storage
    from app.core.database import SessionLocal, get_engine
    from app.services.config_import import import_legacy_system_configs
    from app.services.job_runs_prune import mark_interrupted_job_runs
    from app.services.member_sync import sync_users_and_members
    from app.services.scheduler_runtime import register_scheduler_jobs
    from app.services.seed import seed_data
    from app.services.user_files.backfill import ensure_user_files_registered

    db = SessionLocal()
    try:
        logger.info("startup step 3/9: beijing time storage check")
        ensure_beijing_time_storage(db, get_engine())

        logger.info("startup step 3b: import legacy system_configs into config/")
        import_legacy_system_configs(db)

        logger.info("startup step 4/9: seed data")
        seed_data(db)

        _run_security_checks(db, enforce=enforce_security_checks)

        logger.info("startup step 7/9: sync users and members")
        sync_users_and_members(db)

        logger.info("startup step 8/9: user files backfill")
        ensure_user_files_registered(db)

        interrupted = mark_interrupted_job_runs(db)
        if interrupted:
            logger.warning("startup: marked %s interrupted job run(s) as error", interrupted)

        logger.info("startup step 9/9: register scheduler jobs (run_steam_once=%s)", run_steam_once)
        register_scheduler_jobs(scheduler, db, run_steam_once=run_steam_once)
    finally:
        db.close()


def start_background_services() -> None:
    """TexTeller 权重补齐（后台线程，进程内只起一次）与三狗出没轮询（幂等）。"""
    global _texteller_started
    from app.services.articles.texteller import ensure_texteller_models
    from app.services.tarkov import goon_tracker as goon_tracker_svc

    with _texteller_lock:
        if not _texteller_started:
            _texteller_started = True

            def _ensure_texteller() -> None:
                try:
                    ensure_texteller_models()
                except Exception:
                    logger.exception("texteller model ensure failed")

            threading.Thread(
                target=_ensure_texteller,
                name="texteller-ensure",
                daemon=True,
            ).start()
    goon_tracker_svc.start_poller()
