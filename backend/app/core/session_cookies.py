"""登录会话 Cookie 与 Double-Submit CSRF（与 Bearer 并存）。"""

from __future__ import annotations

import hmac
import secrets
from typing import Any

from fastapi import Request, Response
from fastapi import WebSocket

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User

ACCESS_COOKIE = "zhange_access"
CSRF_COOKIE = "zhange_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def csrf_tokens_match(cookie: str | None, header: str | None) -> bool:
    a = (cookie or "").strip()
    b = (header or "").strip()
    if not a or not b or len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def cookie_secure(request: Request) -> bool:
    if get_settings().is_production:
        return True
    return request.url.scheme == "https"


def _cookie_max_age() -> int:
    from app.services.auth_config import get_access_token_expire_minutes

    return max(60, int(get_access_token_expire_minutes()) * 60)


def attach_session_cookies(
    response: Response,
    access_token: str,
    request: Request,
) -> None:
    max_age = _cookie_max_age()
    secure = cookie_secure(request)
    csrf = secrets.token_urlsafe(32)
    common: dict[str, Any] = {
        "path": "/",
        "max_age": max_age,
        "samesite": "lax",
        "secure": secure,
    }
    response.set_cookie(ACCESS_COOKIE, access_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)


def clear_session_cookies(response: Response, request: Request) -> None:
    # 清除须与写入时的 Path / Secure / SameSite 一致，否则生产 Secure Cookie 删不掉
    secure = cookie_secure(request)
    response.delete_cookie(
        ACCESS_COOKIE,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def issue_session(response: Response, request: Request, user: User) -> str:
    token = create_access_token(user.username, user_id=user.id)
    attach_session_cookies(response, token, request)
    return token


def access_token_from_websocket(websocket: WebSocket, first: dict) -> str:
    cookie = (websocket.cookies.get(ACCESS_COOKIE) or "").strip()
    if cookie:
        return cookie
    return str((first or {}).get("token") or "").strip()
