from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, members, profile, steam
from app.api import settings as settings_api
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.schema_ensure import ensure_schema
from app.models import cs2_match as _cs2_match  # noqa: F401
from app.models import job_run as _job_run  # noqa: F401
from app.models import member as _member  # noqa: F401
from app.models import play_session as _play_session  # noqa: F401
from app.models import presence_segment as _presence_segment  # noqa: F401
from app.models import register_challenge as _register_challenge  # noqa: F401
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
app.include_router(api)

upload_root = _ensure_upload_root()
app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
