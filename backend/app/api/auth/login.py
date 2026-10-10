from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import (
    auth_limiter,
    clear_login_failures,
    client_ip,
    ensure_login_not_locked,
    record_login_failure,
)
from app.core.security import bump_token_version, verify_login_password
from app.core.session_cookies import clear_session_cookies, issue_session
from app.models.user import User
from app.schemas import LoginRequest, TokenResponse
from app.services.account_anonymize import user_is_anonymized

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip = client_ip(request)
    account = body.username.strip()
    auth_limiter.hit(f"login:ip:{ip}", limit=20, window_sec=600)
    auth_limiter.hit(f"login:account:{account.lower()}", limit=10, window_sec=600)
    ensure_login_not_locked(account)

    if "@" in account:
        user = db.query(User).filter(User.email == account.lower()).first()
    else:
        user = db.query(User).filter(User.username == account).first()
    if (
        not user
        or user_is_anonymized(user)
        or not verify_login_password(body.password, user.password_hash)
    ):
        record_login_failure(account)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )
    clear_login_failures(account)
    if user.email and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成邮箱验证",
        )
    token = issue_session(response, request, user)
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    clear_session_cookies(response, request)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """作废本账号在所有设备上的登录（含当前），之后须重新登录。"""
    bump_token_version(user)
    db.commit()
    clear_session_cookies(response, request)
    return {"ok": True, "message": "已退出所有设备"}
