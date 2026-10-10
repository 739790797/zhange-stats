"""个人中心日常任务列表：platform / page / page_size 超界直接 422，不进查询。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.profile import me
from app.core.database import Base, get_db
from app.core.security import create_user_access_token
from app.models.user import User, UserRole

PATHS = ["/api/profile/daily-tasks", "/api/profile/daily-task-logs"]


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    def _db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    api = FastAPI()
    api.include_router(me.router, prefix="/api")
    api.dependency_overrides[get_db] = _db
    with SessionLocal() as db:
        user = User(
            username="alice",
            email="alice@example.com",
            display_name="alice",
            password_hash="unused",
            role=UserRole.user,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        token = create_user_access_token(user)
    test_client = TestClient(api)
    test_client.headers["Authorization"] = f"Bearer {token}"
    yield test_client
    engine.dispose()


@pytest.mark.parametrize("path", PATHS)
def test_in_bounds_query_is_served(client, path: str) -> None:
    assert client.get(path, params={"page": 1, "page_size": 100}).status_code == 200


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "params",
    [{"platform": "x" * 33}, {"page": 0}, {"page_size": 0}, {"page_size": 101}],
)
def test_out_of_bounds_query_is_rejected(client, path: str, params: dict) -> None:
    assert client.get(path, params=params).status_code == 422
