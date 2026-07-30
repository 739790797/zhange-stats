from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, games, members, records, stats
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models import game as _game  # noqa: F401
from app.models import match_record as _match_record  # noqa: F401
from app.models import member as _member  # noqa: F401
from app.models import user as _user  # noqa: F401
from app.services.seed import seed_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
    yield


settings = get_settings()
app = FastAPI(title="CircleStats", description="圈子战绩", lifespan=lifespan)

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
api.include_router(games.router)
api.include_router(records.router)
api.include_router(stats.router)
app.include_router(api)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
