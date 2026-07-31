from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, members, profile, steam, update
from app.api import settings as settings_api
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.schema_ensure import ensure_schema
from app.models import job_run as _job_run  # noqa: F401
from app.models import member as _member  # noqa: F401
from app.models import play_session as _play_session  # noqa: F401
from app.models import presence_segment as _presence_segment  # noqa: F401
from app.models import register_challenge as _register_challenge  # noqa: F401
from app.models import steam_friend as _steam_friend  # noqa: F401
from app.models import system_config as _system_config  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.services.member_sync import sync_users_and_members
from app.services.seed import seed_data
from app.services.steam_poller import poll_job_wrapper

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
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    _ensure_upload_root()
    db = SessionLocal()
    try:
        seed_data(db)
        sync_users_and_members(db)
    finally:
        db.close()

    settings = get_settings()
    started = False
    if settings.STEAM_POLL_ENABLED and settings.STEAM_API_KEY:
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

    if started and not scheduler.running:
        scheduler.start()

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
api.include_router(steam.router)
api.include_router(update.router)
app.include_router(api)

upload_root = _ensure_upload_root()
app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")


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
