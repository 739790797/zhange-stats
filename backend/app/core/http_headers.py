"""请求 ID、安全头、CSP（Report-Only 或 enforce）。生产反代也可再写一遍。"""

from __future__ import annotations

import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.biz_logging import log_context
from app.core.config import get_settings

REQUEST_ID_HEADER = b"x-request-id"
_MAX_RID = 128

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://static.geetest.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' ws: wss: https:; "
    "font-src 'self'; "
    "frame-src 'self' https://static.geetest.com https://gcaptcha4.geetest.com; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "report-uri /api/csp-report"
)

_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-frame-options", b"DENY"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]


def parse_request_id(header_value: str | None) -> str:
    text = (header_value or "").strip()
    if text and len(text) <= _MAX_RID and all(32 <= ord(c) < 127 for c in text):
        return text
    return str(uuid.uuid4())


def _header_from_scope(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers") or []:
        if key.lower() == name:
            return value.decode("latin-1")
    return None


def _is_https(scope: Scope) -> bool:
    proto = _header_from_scope(scope, b"x-forwarded-proto")
    if proto and proto.split(",")[0].strip().lower() == "https":
        return True
    return str(scope.get("scheme") or "") == "https"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = parse_request_id(_header_from_scope(scope, REQUEST_ID_HEADER))
        https = _is_https(scope)
        settings = get_settings()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                existing = {k.lower() for k, _ in headers}
                for key, value in _SECURITY_HEADERS:
                    if key not in existing:
                        headers.append((key, value))
                if settings.is_production and https:
                    if b"strict-transport-security" not in existing:
                        headers.append(
                            (
                                b"strict-transport-security",
                                b"max-age=31536000; includeSubDomains",
                            )
                        )
                csp_name = (
                    b"content-security-policy"
                    if settings.CSP_ENFORCE
                    else b"content-security-policy-report-only"
                )
                if csp_name not in existing:
                    headers.append((csp_name, CSP_POLICY.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        with log_context(request_id=request_id):
            await self.app(scope, receive, send_wrapper)
