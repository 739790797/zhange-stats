"""登录会话 Cookie 与 Double-Submit CSRF（与 Bearer 并存）。"""

from __future__ import annotations

import hmac
import secrets
from typing import Any

from fastapi import Request, Response
from fastapi import WebSocket

from app.core.config import get_settings
from app.core.security import create_user_access_token
from app.models.user import User

ACCESS_COOKIE = "zhange_access"
CSRF_COOKIE = "zhange_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
# 只随 QQ 回调（/api/auth/qq/callback）发送；Lax 下从 graph.qq.com 顶层跳回时仍会带上
QQ_OAUTH_NONCE_COOKIE = "zhange_qq_nonce"
QQ_OAUTH_NONCE_PATH = "/api/auth/qq"


def csrf_tokens_match(cookie: str | None, header: str | None) -> bool:
    a = (cookie or "").strip()
    b = (header or "").strip()
    if not a or not b or len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    # 反代终结 TLS 时看首段 X-Forwarded-Proto；伪造成 https 只会让伪造者自己的 Cookie 存不下
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0]
    return proto.strip().lower() == "https"


def cookie_secure(request: Request, *, setup_response: bool = False) -> bool:
    """HTTPS 一律 Secure；生产即使是 HTTP 也 Secure，仅安装向导建管理员那一次例外（否则装完即掉线）。"""
    if request_is_https(request):
        return True
    return get_settings().is_production and not setup_response


def _cookie_max_age() -> int:
    from app.services.auth_config import get_access_token_expire_minutes

    return max(60, int(get_access_token_expire_minutes()) * 60)


def attach_session_cookies(
    response: Response,
    access_token: str,
    request: Request,
    *,
    setup_response: bool = False,
) -> None:
    max_age = _cookie_max_age()
    secure = cookie_secure(request, setup_response=setup_response)
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


def set_qq_oauth_nonce_cookie(
    response: Response, request: Request, nonce: str, *, max_age: int
) -> None:
    response.set_cookie(
        QQ_OAUTH_NONCE_COOKIE,
        nonce,
        path=QQ_OAUTH_NONCE_PATH,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(request),
    )


def clear_qq_oauth_nonce_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        QQ_OAUTH_NONCE_COOKIE,
        path=QQ_OAUTH_NONCE_PATH,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(request),
    )


def issue_session(response: Response, request: Request, user: User) -> str:
    token = create_user_access_token(user)
    attach_session_cookies(response, token, request)
    return token


def access_token_from_websocket(websocket: WebSocket, first: dict) -> str:
    cookie = (websocket.cookies.get(ACCESS_COOKIE) or "").strip()
    if cookie:
        return cookie
    return str((first or {}).get("token") or "").strip()
