"""管理员高危操作邮箱验证码（步进）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.auth.helpers import (
    PURPOSE_STEPUP,
    _consume_register_challenge,
    _delivery_user_message,
    _upsert_register_challenge,
)
from app.api.auth.schemas import RegisterResponse
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.rate_limit import auth_limiter, client_ip
from app.models.user import User

router = APIRouter()


def consume_admin_step_up(db: Session, user: User, code: str | None) -> None:
    if not user.email or not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先在个人中心绑定并验证邮箱",
        )
    raw = (code or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入邮箱验证码",
        )
    _consume_register_challenge(db, user.email, raw, purpose=PURPOSE_STEPUP)


def require_admin_step_up(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    x_step_up_code: Annotated[str | None, Header(alias="X-Step-Up-Code")] = None,
) -> User:
    consume_admin_step_up(db, user, x_step_up_code)
    return user


@router.post("/step-up/send", response_model=RegisterResponse)
def send_step_up_code(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> RegisterResponse:
    if not user.email or not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先在个人中心绑定并验证邮箱",
        )
    ip = client_ip(request)
    email = user.email.strip().lower()
    auth_limiter.hit(f"step-up:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"step-up:uid:{user.id}", limit=5, window_sec=600)
    auth_limiter.hit(f"step-up:email:{email}", limit=5, window_sec=600)
    _, delivery = _upsert_register_challenge(db, email, purpose=PURPOSE_STEPUP)
    msg = _delivery_user_message(
        delivery,
        sent="验证码已发送",
        logged="验证码已输出到服务端日志（邮件未配置）",
    )
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])
