from contextlib import asynccontextmanager
from pathlib import Path
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, exilium, jobs, members, profile, skland, steam, taygedo, update
from app.api import settings as settings_api
from app.core.beijing_time_migrate import ensure_beijing_time_storage
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.local_dev_hooks import import_steam_fake
from app.core.migrate import run_migrations
from app.core.timeutil import BEIJING
from app.models import arknights as _arknights  # noqa: F401
from app.models import exilium as _exilium  # noqa: F401
from app.models import job_run as _job_run  # noqa: F401
from app.models import member as _member  # noqa: F401
from app.models import play_session as _play_session  # noqa: F401
from app.models import presence_segment as _presence_segment  # noqa: F401
from app.models import register_challenge as _register_challenge  # noqa: F401
from app.models import skland as _skland  # noqa: F401
from app.models import steam_app as _steam_app  # noqa: F401
from app.models import steam_friend as _steam_friend  # noqa: F401
from app.models import system_config as _system_config  # noqa: F401
from app.models import taygedo as _taygedo  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.services.arknights_box_compare import box_sync_job_wrapper as arknights_box_sync_job_wrapper
from app.services.exilium_checkin import checkin_job_wrapper as exilium_checkin_job_wrapper
from app.services.member_sync import sync_users_and_members
from app.services.seed import seed_data
from app.services.skland_checkin import checkin_job_wrapper as skland_checkin_job_wrapper
from app.services.steam_poller import poll_job_wrapper
from app.services.taygedo_checkin import checkin_job_wrapper as taygedo_checkin_job_wrapper

scheduler = BackgroundScheduler()


def _ensure_upload_root() -> Path:
    settings = get_settings()
    path = Path(settings.UPLOAD_DIR).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    (path / "avatars").mkdir(parents=True, exist_ok=True)
    return path


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    _ensure_upload_root()
    db = SessionLocal()
    try:
        ensure_beijing_time_storage(db, engine)
        seed_data(db)
        sync_users_and_members(db)
    finally:
        db.close()

    settings = get_settings()
    started = False
    steam_fake = import_steam_fake() if settings.STEAM_FAKE_POLL else None
    if settings.STEAM_FAKE_POLL and steam_fake is not None:
        db = SessionLocal()
        try:
            steam_fake.ensure_local_fake_data(db)
        finally:
            db.close()
        scheduler.add_job(
            steam_fake.fake_poll_job_wrapper,
            "interval",
            minutes=max(1, settings.STEAM_POLL_INTERVAL_MINUTES),
            id="steam_presence",
            replace_existing=True,
            max_instances=1,
        )
        started = True
        steam_fake.fake_poll_job_wrapper()
    elif settings.STEAM_FAKE_POLL and steam_fake is None:
        import logging

        logging.getLogger("zhange.main").warning(
            "STEAM_FAKE_POLL=true 但未找到 local_dev.steam_fake，已跳过假监控"
        )
    elif settings.STEAM_POLL_ENABLED and settings.STEAM_API_KEY:
        scheduler.add_job(
            poll_job_wrapper,
            "interval",
            minutes=max(1, settings.STEAM_POLL_INTERVAL_MINUTES),
            id="steam_presence",
            replace_existing=True,
            max_instances=1,
        )
        started = True
        poll_job_wrapper()

    if settings.SKLAND_CHECKIN_ENABLED:
        hour = max(0, min(23, int(settings.SKLAND_CHECKIN_HOUR)))
        minute = max(0, min(59, int(settings.SKLAND_CHECKIN_MINUTE)))
        scheduler.add_job(
            skland_checkin_job_wrapper,
            "cron",
            hour=hour,
            minute=minute,
            timezone=BEIJING,
            id="skland_checkin",
            replace_existing=True,
            max_instances=1,
        )
        started = True

    if settings.ARKNIGHTS_BOX_SYNC_ENABLED:
        hour = max(0, min(23, int(settings.ARKNIGHTS_BOX_SYNC_HOUR)))
        minute = max(0, min(59, int(settings.ARKNIGHTS_BOX_SYNC_MINUTE)))
        scheduler.add_job(
            arknights_box_sync_job_wrapper,
            "cron",
            hour=hour,
            minute=minute,
            timezone=BEIJING,
            id="arknights_box_sync",
            replace_existing=True,
            max_instances=1,
        )
        started = True

    if settings.TAYGEDO_CHECKIN_ENABLED:
        hour = max(0, min(23, int(settings.TAYGEDO_CHECKIN_HOUR)))
        minute = max(0, min(59, int(settings.TAYGEDO_CHECKIN_MINUTE)))
        scheduler.add_job(
            taygedo_checkin_job_wrapper,
            "cron",
            hour=hour,
            minute=minute,
            timezone=BEIJING,
            id="taygedo_checkin",
            replace_existing=True,
            max_instances=1,
        )
        started = True

    if settings.EXILIUM_CHECKIN_ENABLED:
        hour = max(0, min(23, int(settings.EXILIUM_CHECKIN_HOUR)))
        minute = max(0, min(59, int(settings.EXILIUM_CHECKIN_MINUTE)))
        scheduler.add_job(
            exilium_checkin_job_wrapper,
            "cron",
            hour=hour,
            minute=minute,
            timezone=BEIJING,
            id="exilium_checkin",
            replace_existing=True,
            max_instances=1,
        )
        started = True

    # 延后启动调度器，避免 Windows 上 BackgroundScheduler 卡住 uvicorn lifespan 收尾日志
    if started and not scheduler.running:

        def _start_scheduler() -> None:
            if not scheduler.running:
                scheduler.start()

        threading.Thread(
            target=_start_scheduler,
            name="apscheduler-start",
            daemon=True,
        ).start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(
    title="战鸽数据",
    description="Zhange Stats · Steam 游玩统计与圈子成员管理",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(members.router)
api.include_router(profile.router)
api.include_router(settings_api.router)
api.include_router(jobs.router)
api.include_router(steam.router)
api.include_router(skland.router)
api.include_router(taygedo.router)
api.include_router(exilium.router)
api.include_router(update.router)
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
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION}


_static_dir = Path(settings.STATIC_DIR).expanduser() if settings.STATIC_DIR else None
if _static_dir and not _static_dir.is_absolute():
    _static_dir = (Path.cwd() / _static_dir).resolve()
elif _static_dir:
    _static_dir = _static_dir.resolve()

if _static_dir and _static_dir.is_dir():
    assets_dir = _static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

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
            return FileResponse(candidate)
        index = _static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend not found")
        return FileResponse(index)
