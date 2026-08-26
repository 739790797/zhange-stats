"""未初始化时拦截业务 API，仅放行安装向导与健康检查。"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import SessionLocal
from app.services.setup import is_setup_complete_cached, mark_setup_complete, needs_setup


def _is_allowed_during_setup(path: str) -> bool:
    if path == "/health" or path.startswith("/health/"):
        return True
    if path in ("/docs", "/redoc", "/openapi.json"):
        return True
    if path.startswith("/docs/") or path.startswith("/redoc/"):
        return True
    if path == "/api/setup" or path.startswith("/api/setup/"):
        return True
    if not path.startswith("/api/"):
        return True
    return False


def _peek_setup_required() -> bool:
    if is_setup_complete_cached():
        return False
    db = SessionLocal()
    try:
        required = needs_setup(db)
        if not required:
            mark_setup_complete()
        return required
    except Exception:  # noqa: BLE001
        return False
    finally:
        db.close()


class SetupRequiredMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or "/"
        if _is_allowed_during_setup(path) or is_setup_complete_cached():
            await self.app(scope, receive, send)
            return

        required = _peek_setup_required()
        if not required:
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=503,
            content={
                "detail": "系统尚未初始化，请先完成安装向导",
                "code": "SETUP_REQUIRED",
            },
        )
        await response(scope, receive, send)
