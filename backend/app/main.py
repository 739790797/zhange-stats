from contextlib import asynccontextmanager
import logging
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, exilium, guides, jobs, kujiequ, members, mihoyo, profile, setup, skland, steam, taygedo
from app.api import app_update as app_update_api
from app.api import runtime_health as runtime_health_api
from app.api import runtime_logs as runtime_logs_api
from app.api import settings as settings_api
from app.core.beijing_time_migrate import ensure_beijing_time_storage
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.http_client import close_http_client
from app.core.migrate import run_migrations
from app.core.paths import hydrate_legacy_runtime, resolve_install_dir, resolve_runtime_path
from app.core.request_log_middleware import RequestLogMiddleware
from app.core.runtime_log_buffer import install_runtime_log_buffer
from app.core.setup_middleware import SetupRequiredMiddleware
from app.models import arknights as _arknights  # noqa: F401
from app.models import arknights_rogue as _arknights_rogue  # noqa: F401
from app.models import exilium as _exilium  # noqa: F401
from app.models import kujiequ as _kujiequ  # noqa: F401
from app.models import mihoyo as _mihoyo  # noqa: F401
from app.models import job_run as _job_run  # noqa: F401
from app.models import member as _member  # noqa: F401
from app.models import play_session as _play_session  # noqa: F401
from app.models import presence_segment as _presence_segment  # noqa: F401
from app.models import register_challenge as _register_challenge  # noqa: F401
from app.models import skland as _skland  # noqa: F401
from app.models import steam_app as _steam_app  # noqa: F401
from app.models import system_config as _system_config  # noqa: F401
from app.models import tarkov as _tarkov  # noqa: F401
from app.models import minecraft as _minecraft  # noqa: F401
from app.models import taygedo as _taygedo  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.services.seed import seed_data
from app.services.scheduler_runtime import register_scheduler_jobs
from app.services.member_sync import sync_users_and_members

logger = logging.getLogger("zhange.startup")
scheduler = BackgroundScheduler()
install_runtime_log_buffer()

_HEALTH_DB_TTL_SEC = 1.0
_health_db_ok: bool | None = None
_health_db_at = 0.0


class ImmutableStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _ping_database() -> bool:
    """SELECT 1，1 秒内复用结果，避免探针打满连接池。"""
    global _health_db_ok, _health_db_at
    now = time.monotonic()
    if _health_db_ok is not None and now - _health_db_at < _HEALTH_DB_TTL_SEC:
        return _health_db_ok
    from sqlalchemy import text

    ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    _health_db_ok = ok
    _health_db_at = now
    return ok


def _ensure_upload_root() -> Path:
    path = get_settings().upload_dir_path
    (path / "avatars").mkdir(parents=True, exist_ok=True)
    return path


@asynccontextmanager
async def lifespan(_: FastAPI):
    cfg = get_settings()
    logger.info(
        "startup begin version=%s env=%s install_dir=%s",
        cfg.APP_VERSION,
        cfg.APP_ENV,
        (cfg.APP_INSTALL_DIR or "").strip() or "(unset)",
    )

    logger.info("startup step 1/8: alembic migrate")
    try:
        run_migrations()
    except Exception:
        logger.exception(
            "startup migrate failed — process will exit; "
            "fix the migration or run scripts/emergency_update.sh on the host"
        )
        raise

    logger.info("startup step 2/8: ensure upload root (%s)", cfg.UPLOAD_DIR)
    upload_path = _ensure_upload_root()
    hydrate_legacy_runtime(
        dest_data=cfg.data_dir_path,
        install=resolve_install_dir(configured=cfg.APP_INSTALL_DIR),
    )
    logger.info("startup step 2/8 done: upload_root=%s data_root=%s", upload_path, cfg.data_dir_path)

    db = SessionLocal()
    try:
        logger.info("startup step 3/8: beijing time storage check")
        ensure_beijing_time_storage(db, engine)

        logger.info("startup step 4/8: seed data")
        seed_data(db)

        from app.services.security_bootstrap import (
            check_admin_password_health,
            check_email_code_log_policy,
        )

        logger.info("startup step 5/8: email code log policy")
        check_email_code_log_policy()

        logger.info("startup step 6/8: admin password health")
        check_admin_password_health(db)

        logger.info("startup step 7/8: sync users and members")
        sync_users_and_members(db)

        logger.info("startup step 8/8: register scheduler jobs (run_steam_once=true)")
        register_scheduler_jobs(scheduler, db, run_steam_once=True)
    finally:
        db.close()

    logger.info(
        "startup complete version=%s scheduler_running=%s static_dir=%s",
        cfg.APP_VERSION,
        scheduler.running,
        (cfg.STATIC_DIR or "").strip() or "(unset)",
    )
    yield

    logger.info("shutdown begin")
    close_http_client()
    if scheduler.running:
        logger.info("shutdown: stopping scheduler")
        scheduler.shutdown(wait=False)
    logger.info("shutdown complete")


settings = get_settings()
_disable_docs = settings.is_production
app = FastAPI(
    title="战鸽数据",
    description="Zhange Stats · Steam 游玩统计与圈子成员管理",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    docs_url=None if _disable_docs else "/docs",
    redoc_url=None if _disable_docs else "/redoc",
    openapi_url=None if _disable_docs else "/openapi.json",
)

_cors_origins = settings.cors_origin_list
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if _cors_origins:
    _cors_kwargs["allow_origins"] = _cors_origins
else:
    # 本地 Vite（任意端口）；生产同域部署一般不触发跨域
    _cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

app.add_middleware(RequestLogMiddleware)
app.add_middleware(CORSMiddleware, **_cors_kwargs)
app.add_middleware(SetupRequiredMiddleware)

api = APIRouter(prefix="/api")
api.include_router(setup.router)
api.include_router(auth.router)
api.include_router(members.router)
api.include_router(profile.router)
api.include_router(settings_api.router)
api.include_router(app_update_api.router)
api.include_router(runtime_logs_api.router)
api.include_router(runtime_health_api.router)
api.include_router(jobs.router)
api.include_router(steam.router)
api.include_router(skland.router)
api.include_router(taygedo.router)
api.include_router(exilium.router)
api.include_router(kujiequ.router)
api.include_router(mihoyo.router)
api.include_router(guides.router)
app.include_router(api)

# 只挂载头像子目录，避免 DATA_DIR / 上传根目录下的私密文件被公开访问
upload_root = _ensure_upload_root()
avatars_root = upload_root / "avatars"
app.mount(
    "/uploads/avatars",
    StaticFiles(directory=str(avatars_root)),
    name="uploads_avatars",
)


@app.get("/health")
def health():
    """存活/就绪探测；数据库不通时 HTTP 503（编排器可摘流量）。"""
    from fastapi.responses import JSONResponse

    db_ok = _ping_database()
    sched_ok = bool(scheduler.running) if scheduler else False
    status = "ok" if db_ok else "degraded"
    body = {
        "status": status,
        "version": settings.APP_VERSION,
        "database": "ok" if db_ok else "error",
        "scheduler": "ok" if sched_ok else "stopped",
    }
    return JSONResponse(content=body, status_code=200 if db_ok else 503)


_static_dir = (
    resolve_runtime_path(settings.STATIC_DIR, configured_install=settings.APP_INSTALL_DIR)
    if settings.STATIC_DIR
    else None
)

if _static_dir and _static_dir.is_dir():
    assets_dir = _static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # API / uploads / health / docs 已由上方路由处理；其余走前端 SPA
        if full_path.startswith(
            ("api/", "uploads/", "health", "docs", "redoc", "openapi.json")
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (_static_dir / full_path).resolve()
        try:
            candidate.relative_to(_static_dir)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not Found") from exc
        if full_path and candidate.is_file():
            resp = FileResponse(candidate)
            if full_path.startswith("assets/"):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        index = _static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend not found")
        resp = FileResponse(index)
        resp.headers["Cache-Control"] = "no-cache"
        return resp
