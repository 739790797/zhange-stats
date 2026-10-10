"""首次安装向导 API。"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.config import get_settings
from app.core.database import configure_engine, get_db
from app.core.file_config import (
    DatabaseSettingsError,
    database_is_configured,
    default_sqlite_rel,
    save_database_settings,
)
from app.core.session_cookies import attach_session_cookies
from app.core.startup import run_post_database_startup, start_background_services
from app.services.auth_config import get_min_password_length
from app.services.setup import (
    SETUP_TOKEN_HEADER,
    SetupError,
    complete_initial_admin,
    delete_setup_token,
    ensure_setup_token,
    is_setup_complete_cached,
    mark_setup_complete,
    needs_setup,
    setup_marker_exists,
    setup_open,
    setup_token_matches,
)

logger = logging.getLogger("zhange.setup")

router = APIRouter(prefix="/setup", tags=["setup"])

_CRED_IN_URL = re.compile(r"(://)[^@/\s]+@")
_TOKEN_LOG_KEY = "setup.token_file"


class SetupStatusOut(BaseModel):
    needs_setup: bool
    needs_database: bool
    needs_admin: bool
    min_password_length: int = 8
    engines: list[str] = Field(default_factory=lambda: ["sqlite", "mysql"])
    sqlite_path: str = ""
    # 为 true 时 POST /api/setup/* 须带 X-Setup-Token（服务器 data 目录下 setup-token 文件的内容）
    token_required: bool = False


class SetupDatabaseRequest(BaseModel):
    engine: str = Field(pattern="^(sqlite|mysql)$")
    url: str = Field(default="", max_length=2000)


class SetupDatabaseResponse(BaseModel):
    ok: bool = True
    message: str
    engine: str
    sqlite_path: str = ""


class SetupAdminRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=64)
    # 72 字节上限由 validate_password 给中文提示
    password: str = Field(min_length=1, max_length=256)


class SetupAdminResponse(BaseModel):
    """会话只在 HttpOnly Cookie 里，响应体不回令牌。"""

    message: str


def _apply_schema() -> None:
    from app.core.migrate import run_migrations

    run_migrations()


def _announce_setup_token() -> None:
    try:
        ensure_setup_token()
    except OSError as exc:
        log_until_change(
            logger, _TOKEN_LOG_KEY, "setup: cannot write install token file (%s)", exc
        )
        return
    clear_log_until_change(_TOKEN_LOG_KEY)


def _check_setup_token(provided: str | None) -> None:
    """调用方已确认向导仍未完成。令牌只在服务器文件里，证明提交者能碰到这台机器。"""
    _announce_setup_token()
    if not setup_token_matches(provided):
        raise HTTPException(
            status_code=403,
            detail="安装令牌缺失或不正确：请填写服务器上 setup-token 文件的内容（路径见服务日志）",
        )


def _redact_db_error(exc: BaseException, url: str) -> str:
    text = " ".join(str(exc).split())
    try:
        from sqlalchemy.engine import make_url

        password = make_url(url).password
    except Exception:  # noqa: BLE001
        password = None
    if password:
        text = text.replace(str(password), "***")
    text = _CRED_IN_URL.sub(r"\1***@", text)
    return f"{exc.__class__.__name__}: {text[:300]}"


def _finish_startup_after_setup() -> None:
    """进程是在未配库状态下启动的：补跑库就绪后的启动步骤，免得装完还要重启才有调度。"""
    from app.main import scheduler

    if scheduler.running:
        return
    try:
        run_post_database_startup(
            scheduler, run_steam_once=True, enforce_security_checks=False
        )
        start_background_services()
    except Exception:  # noqa: BLE001
        logger.exception("setup: post-setup startup failed; restart the service to retry")


@router.get("/status", response_model=SetupStatusOut)
def get_setup_status() -> SetupStatusOut:
    rel = default_sqlite_rel()
    if not database_is_configured():
        _announce_setup_token()
        return SetupStatusOut(
            needs_setup=True,
            needs_database=True,
            needs_admin=True,
            min_password_length=8,
            sqlite_path=rel,
            token_required=True,
        )
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        admin_needed = needs_setup(db)
        still_open = admin_needed and not setup_marker_exists(db)
        if still_open:
            _announce_setup_token()
        return SetupStatusOut(
            needs_setup=admin_needed,
            needs_database=False,
            needs_admin=admin_needed,
            min_password_length=get_min_password_length(db),
            sqlite_path=rel,
            token_required=still_open,
        )
    finally:
        db.close()


@router.post("/database", response_model=SetupDatabaseResponse)
def post_setup_database(
    body: SetupDatabaseRequest,
    x_setup_token: str | None = Header(default=None, alias=SETUP_TOKEN_HEADER),
) -> SetupDatabaseResponse:
    if database_is_configured() or is_setup_complete_cached():
        raise HTTPException(status_code=409, detail="数据库已配置")
    _check_setup_token(x_setup_token)
    engine = body.engine.strip().lower()
    try:
        saved = save_database_settings(engine=engine, url=body.url or "")
    except DatabaseSettingsError as exc:
        if exc.__cause__ is None:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # 驱动报错里可能带主机、账号乃至连接串，只进服务端日志（脱敏后）
        logger.warning(
            "setup: database connection check failed (%s)",
            _redact_db_error(exc.__cause__, body.url or ""),
        )
        raise HTTPException(
            status_code=400,
            detail="无法连接数据库，请检查主机、端口、库名与账号密码",
        ) from exc
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
    x_setup_token: str | None = Header(default=None, alias=SETUP_TOKEN_HEADER),
    db: Session = Depends(get_db),
) -> SetupAdminResponse:
    if not database_is_configured():
        raise HTTPException(status_code=400, detail="请先选择数据库")
    if is_setup_complete_cached() or not setup_open(db):
        raise HTTPException(status_code=409, detail="系统已完成初始化")
    _check_setup_token(x_setup_token)
    try:
        _user, token = complete_initial_admin(
            db,
            email=str(body.email),
            display_name=body.display_name,
            password=body.password,
        )
    except SetupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    delete_setup_token()
    _finish_startup_after_setup()
    mark_setup_complete()
    attach_session_cookies(response, token, request, setup_response=True)
    return SetupAdminResponse(message="初始化完成，已创建管理员账号")
