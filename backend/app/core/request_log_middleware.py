"""HTTP 请求日志：方法 / 路径 / 状态 / 耗时。纯 ASGI，避免 BaseHTTPMiddleware 缓冲。"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.biz_logging import log_context

logger = logging.getLogger("zhange.http")

_SKIP_PREFIXES = (
    "/assets/",
    "/uploads/avatars/",
)
_SKIP_EXACT = frozenset({"/health", "/favicon.ico"})
_SLOW_GET_MS = 200.0


def should_log_request(method: str, path: str, status_code: int, elapsed_ms: float) -> bool:
    """GET 2xx 且快路径不打 INFO；写操作 / 错误 / 慢请求仍记。"""
    if path in _SKIP_EXACT or any(path.startswith(p) for p in _SKIP_PREFIXES):
        return False
    if "/settings/runtime-health" in path or "/settings/runtime-logs" in path:
        return False
    if method.upper() != "GET":
        return True
    if status_code >= 400:
        return True
    return elapsed_ms >= _SLOW_GET_MS


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        method = str(scope.get("method") or "GET")
        if path in _SKIP_EXACT or any(path.startswith(p) for p in _SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return
        if "/settings/runtime-health" in path or "/settings/runtime-logs" in path:
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if not should_log_request(method, path, status_code, elapsed_ms):
                return
            client = "-"
            peer = scope.get("client")
            if peer:
                client = str(peer[0])
            with log_context(
                method=method,
                path=path,
                status=str(status_code),
            ):
                logger.info(
                    "%s %s -> %s %.0fms client=%s",
                    method,
                    path,
                    status_code,
                    elapsed_ms,
                    client,
                )
