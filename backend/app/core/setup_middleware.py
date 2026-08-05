"""未初始化时拦截业务 API，仅放行安装向导与健康检查。"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.database import SessionLocal
from app.services.setup import needs_setup


def _is_allowed_during_setup(path: str) -> bool:
    if path == "/health" or path.startswith("/health/"):
        return True
    if path in ("/docs", "/redoc", "/openapi.json"):
        return True
    if path.startswith("/docs/") or path.startswith("/redoc/"):
        return True
    if path == "/api/setup" or path.startswith("/api/setup/"):
        return True
    # 前端 SPA / 静态资源由前端自己跳转到 /setup
    if not path.startswith("/api/"):
        return True
    return False


class SetupRequiredMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path or "/"
        if _is_allowed_during_setup(path):
            return await call_next(request)

        db = SessionLocal()
        try:
            required = needs_setup(db)
        except Exception:  # noqa: BLE001
            required = False
        finally:
            db.close()

        if not required:
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "detail": "系统尚未初始化，请先完成安装向导",
                "code": "SETUP_REQUIRED",
            },
        )
