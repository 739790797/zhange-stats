"""从当前请求推断对外可访问的前后端基址（env 可选手动覆盖）。"""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request

from app.core.config import get_settings


def _normalize_base(url: str | None) -> str:
    value = (url or "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"http://{value}")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _forwarded_proto(request: Request) -> str:
    raw = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if raw in ("http", "https"):
        return raw
    return request.url.scheme or "http"


def _forwarded_host(request: Request) -> str:
    raw = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if raw:
        return raw
    return (request.headers.get("host") or request.url.netloc or "").strip()


def resolve_backend_base(request: Request) -> str:
    settings = get_settings()
    override = _normalize_base(settings.PUBLIC_BACKEND_URL)
    if override:
        return override
    host = _forwarded_host(request)
    if not host:
        return ""
    return f"{_forwarded_proto(request)}://{host}".rstrip("/")


def resolve_frontend_base(request: Request, *, backend: str | None = None) -> str:
    settings = get_settings()
    override = _normalize_base(settings.PUBLIC_FRONTEND_URL)
    if override:
        return override

    origin = _normalize_base(request.headers.get("origin"))
    if origin:
        return origin

    referer = (request.headers.get("referer") or "").strip()
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    if backend:
        return backend.rstrip("/")
    return resolve_backend_base(request)
