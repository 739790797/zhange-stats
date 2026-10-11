"""从当前请求推断对外可访问的前后端基址（env 可选手动覆盖）。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from starlette.requests import Request

from app.core.config import get_settings
from app.core.cors import resolve_cors_origin_regex


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


def frontend_allowlist(request: Request, *, backend: str | None = None) -> list[str]:
    """OAuth 回跳可去的前端基址：PUBLIC_FRONTEND_URL、后端同源地址、CORS_ORIGINS。"""
    settings = get_settings()
    candidates = [
        settings.PUBLIC_FRONTEND_URL,
        backend or resolve_backend_base(request),
        *settings.cors_origin_list,
    ]
    out: list[str] = []
    for raw in candidates:
        base = _normalize_base(raw)
        if base and base not in out:
            out.append(base)
    return out


def _matches_cors_regex(base: str) -> bool:
    # 与 CORS / WS Origin 同一信任面：非生产默认放行本机 Vite 任意端口，生产只认显式 CORS_ORIGIN_REGEX
    settings = get_settings()
    pattern = resolve_cors_origin_regex(
        settings.CORS_ORIGIN_REGEX, production=settings.is_production
    )
    return bool(pattern and re.fullmatch(pattern, base))


def allowed_frontend_base(
    candidate: str | None, request: Request, *, backend: str | None = None
) -> str:
    """candidate 落在白名单或 CORS 正则内则返回其基址，否则空串。"""
    base = _normalize_base(candidate)
    if not base:
        return ""
    if base in frontend_allowlist(request, backend=backend) or _matches_cors_regex(base):
        return base
    return ""


def resolve_frontend_base(request: Request, *, backend: str | None = None) -> str:
    """回跳前端只在白名单里挑：Origin / Referer 本身可被任意调用方伪造，仅用来在白名单内选一项。"""
    settings = get_settings()
    override = _normalize_base(settings.PUBLIC_FRONTEND_URL)
    if override:
        return override

    for header in ("origin", "referer"):
        picked = allowed_frontend_base(request.headers.get(header), request, backend=backend)
        if picked:
            return picked

    return _normalize_base(backend) or resolve_backend_base(request)
