"""HTTP 请求日志：方法 / 路径 / 状态 / 耗时。"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.biz_logging import log_context

logger = logging.getLogger("zhange.http")

_SKIP_PREFIXES = (
    "/assets/",
    "/uploads/avatars/",
)
_SKIP_EXACT = frozenset({"/health", "/favicon.ico"})

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in _SKIP_EXACT or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)
        if "/settings/runtime-health" in path or "/settings/runtime-logs" in path:
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            client = request.client.host if request.client else "-"
            with log_context(
                method=request.method,
                path=path,
                status=str(status_code),
            ):
                logger.info(
                    "%s %s -> %s %.0fms client=%s",
                    request.method,
                    path,
                    status_code,
                    elapsed_ms,
                    client,
                )
