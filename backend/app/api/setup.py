"""首次安装向导 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import configure_engine, get_db
from app.core.file_config import (
    DatabaseSettingsError,
    database_is_configured,
    default_sqlite_rel,
    save_database_settings,
)
from app.core.session_cookies import attach_session_cookies
from app.services.auth_config import get_min_password_length
from app.services.setup import SetupError, complete_initial_admin, needs_setup

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupStatusOut(BaseModel):
    needs_setup: bool
    needs_database: bool
    needs_admin: bool
    min_password_length: int = 8
    engines: list[str] = Field(default_factory=lambda: ["sqlite", "mysql"])
    sqlite_path: str = ""


class SetupDatabaseRequest(BaseModel):
    engine: str = Field(pattern="^(sqlite|mysql)$")
    url: str = ""


class SetupDatabaseResponse(BaseModel):
    ok: bool = True
    message: str
    engine: str
    sqlite_path: str = ""


class SetupAdminRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class SetupAdminResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"


def _apply_schema() -> None:
    from app.core.migrate import run_migrations

    run_migrations()


@router.get("/status", response_model=SetupStatusOut)
def get_setup_status() -> SetupStatusOut:
    rel = default_sqlite_rel()
    if not database_is_configured():
        return SetupStatusOut(
            needs_setup=True,
            needs_database=True,
            needs_admin=True,
            min_password_length=8,
            sqlite_path=rel,
        )
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        admin_needed = needs_setup(db)
        return SetupStatusOut(
            needs_setup=admin_needed,
            needs_database=False,
            needs_admin=admin_needed,
            min_password_length=get_min_password_length(db),
            sqlite_path=rel,
        )
    finally:
        db.close()


@router.post("/database", response_model=SetupDatabaseResponse)
def post_setup_database(body: SetupDatabaseRequest) -> SetupDatabaseResponse:
    if database_is_configured():
        raise HTTPException(status_code=409, detail="数据库已配置")
    engine = body.engine.strip().lower()
    try:
        saved = save_database_settings(engine=engine, url=body.url or "")
    except DatabaseSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_settings.cache_clear()
    if engine == "sqlite":
        configure_engine()
        _apply_schema()
        return SetupDatabaseResponse(
            message="已使用 SQLite 文件库",
            engine="sqlite",
            sqlite_path=saved["db_path"],
        )
    configure_engine(saved["db_url"])
    _apply_schema()
    return SetupDatabaseResponse(
        message="已连接外部 MySQL/MariaDB",
        engine="mysql",
    )


@router.post("/admin", response_model=SetupAdminResponse)
def post_setup_admin(
    body: SetupAdminRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SetupAdminResponse:
    if not database_is_configured():
        raise HTTPException(status_code=400, detail="请先选择数据库")
    try:
        _user, token = complete_initial_admin(
            db,
            email=str(body.email),
            display_name=body.display_name,
            password=body.password,
        )
    except SetupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    attach_session_cookies(response, token, request)
    return SetupAdminResponse(
        message="初始化完成，已创建管理员账号",
        access_token=token,
    )
