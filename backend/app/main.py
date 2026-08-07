from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, exilium, jobs, kujiequ, members, napcat, profile, setup, skland, steam, taygedo
from app.api import settings as settings_api
from app.core.beijing_time_migrate import ensure_beijing_time_storage
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.migrate import run_migrations
from app.core.setup_middleware import SetupRequiredMiddleware
from app.models import arknights as _arknights  # noqa: F401
from app.models import arknights_rogue as _arknights_rogue  # noqa: F401
from app.models import exilium as _exilium  # noqa: F401
from app.models import kujiequ as _kujiequ  # noqa: F401
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
from app.services.seed import seed_data
from app.services.scheduler_runtime import register_scheduler_jobs
from app.services.member_sync import sync_users_and_members

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
        from app.services.security_bootstrap import (
            check_admin_password_health,
            check_email_code_log_policy,
        )

        check_email_code_log_policy()
        check_admin_password_health(db)
        sync_users_and_members(db)
        register_scheduler_jobs(scheduler, db, run_steam_once=True)
    finally:
        db.close()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(
    title="战鸽数据",
    description="Zhange Stats · Steam 游玩统计与圈子成员管理",
    lifespan=lifespan,
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

app.add_middleware(CORSMiddleware, **_cors_kwargs)
app.add_middleware(SetupRequiredMiddleware)

api = APIRouter(prefix="/api")
api.include_router(setup.router)
api.include_router(auth.router)
api.include_router(members.router)
api.include_router(profile.router)
api.include_router(settings_api.router)
api.include_router(jobs.router)
api.include_router(steam.router)
api.include_router(skland.router)
api.include_router(taygedo.router)
api.include_router(exilium.router)
api.include_router(kujiequ.router)
api.include_router(napcat.router)
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
    from sqlalchemy import text

    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    sched_ok = bool(scheduler.running) if scheduler else False
    status = "ok" if db_ok else "degraded"
    body = {
        "status": status,
        "version": settings.APP_VERSION,
        "database": "ok" if db_ok else "error",
        "scheduler": "ok" if sched_ok else "stopped",
    }
    return JSONResponse(content=body, status_code=200 if db_ok else 503)


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
