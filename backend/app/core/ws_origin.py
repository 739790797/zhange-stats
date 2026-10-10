"""WebSocket 握手 Origin 校验，防跨站 WebSocket 劫持（Cookie 会话会被浏览器自动带上）。"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from starlette.websockets import WebSocket

from app.core.biz_logging import log_until_change
from app.core.config import get_settings
from app.core.cors import resolve_cors_origin_regex

logger = logging.getLogger(__name__)

CLOSE_ORIGIN_FORBIDDEN = 4403


def _normalize_origin(value: str | None) -> str:
    text = (value or "").strip().rstrip("/")
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"http://{text}")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def _request_hosts(websocket: WebSocket) -> set[str]:
    hosts: set[str] = set()
    for name in ("host", "x-forwarded-host"):
        raw = (websocket.headers.get(name) or "").split(",")[0].strip().lower()
        if raw:
            hosts.add(raw)
    return hosts


def origin_allowed(origin: str, *, request_hosts: set[str]) -> bool:
    normalized = _normalize_origin(origin)
    if not normalized:
        return False
    if urlparse(normalized).netloc in request_hosts:
        return True
    settings = get_settings()
    for base in (settings.PUBLIC_FRONTEND_URL, settings.PUBLIC_BACKEND_URL, *settings.cors_origin_list):
        if normalized == _normalize_origin(base):
            return True
    pattern = resolve_cors_origin_regex(
        settings.CORS_ORIGIN_REGEX,
        production=settings.is_production,
    )
    return bool(pattern and re.fullmatch(pattern, normalized))


def websocket_origin_allowed(websocket: WebSocket) -> bool:
    """浏览器握手必带 Origin；无 Origin 的非浏览器客户端只能靠首帧 token，不受 Cookie 劫持影响。"""
    origin = (websocket.headers.get("origin") or "").strip()
    if not origin:
        return True
    hosts = _request_hosts(websocket)
    if origin_allowed(origin, request_hosts=hosts):
        return True
    log_until_change(
        logger,
        "ws_origin.rejected",
        "websocket origin rejected origin=%s host=%s path=%s",
        origin[:200],
        ",".join(sorted(hosts))[:200],
        websocket.url.path,
    )
    return False
