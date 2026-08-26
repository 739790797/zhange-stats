from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip = client_ip(request)
    account = body.username.strip()
    auth_limiter.hit(f"login:ip:{ip}", limit=20, window_sec=600)
    auth_limiter.hit(f"login:account:{account.lower()}", limit=10, window_sec=600)

    if "@" in account:
        user = db.query(User).filter(User.email == account.lower()).first()
    else:
        user = db.query(User).filter(User.username == account).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )
    if user.email and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成邮箱验证",
        )
    token = create_access_token(user.username, user_id=user.id)
    return TokenResponse(access_token=token)
