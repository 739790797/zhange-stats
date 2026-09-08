"""自助注销账号。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth.helpers import (
    PURPOSE_DELETE,
    _consume_register_challenge,
    _delivery_user_message,
    _upsert_register_challenge,
)
from app.api.auth.schemas import RegisterResponse
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import auth_limiter, client_ip
from app.core.session_cookies import clear_session_cookies
from app.models.user import User
from app.services.account_anonymize import (
    AccountAnonymizeError,
    anonymize_user_account,
)

router = APIRouter()


class DeleteAccountRequest(BaseModel):
    code: str = Field(min_length=4, max_length=16)


@router.post("/account/delete-code", response_model=RegisterResponse)
def send_delete_account_code(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RegisterResponse:
    if not user.email or not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先绑定并验证邮箱后再注销",
        )
    ip = client_ip(request)
    email = user.email.strip().lower()
    auth_limiter.hit(f"send-code:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"send-code:email:{email}", limit=5, window_sec=600)
    _, delivery = _upsert_register_challenge(db, email, purpose=PURPOSE_DELETE)
    msg = _delivery_user_message(
        delivery,
        sent="验证码已发送",
        logged="验证码已输出到服务端日志（邮件未配置）",
    )
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/account/delete")
def delete_own_account(
    body: DeleteAccountRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not user.email or not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先绑定并验证邮箱后再注销",
        )
    ip = client_ip(request)
    email = user.email.strip().lower()
    auth_limiter.hit(f"delete-account:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"delete-account:uid:{user.id}", limit=10, window_sec=600)
    _consume_register_challenge(db, email, body.code.strip(), purpose=PURPOSE_DELETE)
    try:
        anonymize_user_account(db, user, actor_id=user.id)
        db.commit()
    except AccountAnonymizeError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    clear_session_cookies(response, request)
    return {"ok": True, "message": "账号已注销"}
