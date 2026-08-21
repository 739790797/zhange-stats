from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.auth.helpers import (
    PURPOSE_RESET,
    _consume_register_challenge,
    _upsert_register_challenge,
)
from app.api.auth.schemas import (
    ResetPasswordRequest,
    ResetPasswordResponse,
    SendResetPasswordCodeRequest,
)
from app.core.database import get_db
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.auth_config import get_min_password_length
from app.services.password_policy import (
    PasswordPolicyError,
    invalidate_weak_password_cache,
    validate_password,
)

router = APIRouter()

_FUZZY_SEND_MSG = "若该邮箱可找回密码，验证码已发送"


@router.post("/send-reset-password-code", response_model=ResetPasswordResponse)
def send_reset_password_code(
    body: SendResetPasswordCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"reset-code:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"reset-code:email:{email}", limit=5, window_sec=600)

    user = (
        db.query(User)
        .filter(User.email == email, User.email_verified.is_(True))
        .first()
    )
    if not user:
        return ResetPasswordResponse(
            message=_FUZZY_SEND_MSG,
            email=email,
            delivery="skipped",
        )

    _, delivery = _upsert_register_challenge(db, email, purpose=PURPOSE_RESET)
    msg = _FUZZY_SEND_MSG
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志（邮件未配置或发送失败）"
    return ResetPasswordResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    code = body.code.strip()
    auth_limiter.hit(f"reset-password:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"reset-password:email:{email}", limit=10, window_sec=600)

    user = (
        db.query(User)
        .filter(User.email == email, User.email_verified.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="重置失败，请检查邮箱与验证码")

    _consume_register_challenge(db, email, code, purpose=PURPOSE_RESET)

    try:
        new_password = validate_password(
            body.new_password,
            username=user.username,
            min_length=get_min_password_length(db),
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    invalidate_weak_password_cache(user.password_hash)
    user.password_hash = hash_password(new_password)
    db.commit()
    return ResetPasswordResponse(message="密码已重置，请使用新密码登录", email=email)
