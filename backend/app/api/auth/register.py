from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.auth.helpers import (
    PURPOSE_REGISTER,
    _consume_register_challenge,
    _gen_username,
    _upsert_register_challenge,
)
from app.api.auth.schemas import (
    RegisterRequest,
    RegisterResponse,
    ResendCodeRequest,
    SendRegisterCodeRequest,
    VerifyEmailRequest,
)
from app.core.database import get_db
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole
from app.services.member_sync import ensure_user_member

router = APIRouter()


@router.post("/send-register-code", response_model=RegisterResponse)
def send_register_code(
    body: SendRegisterCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"send-code:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"send-code:email:{email}", limit=5, window_sec=600)

    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        # 不暴露邮箱是否已注册
        return RegisterResponse(
            message="若该邮箱可注册，验证码已发送",
            email=email,
            delivery="skipped",
        )
    _, delivery = _upsert_register_challenge(db, email, purpose=PURPOSE_REGISTER)
    msg = "若该邮箱可注册，验证码已发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志（邮件未配置或发送失败）"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/register", response_model=RegisterResponse)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    auth_limiter.hit(f"register:ip:{ip}", limit=10, window_sec=600)

    email = str(body.email).strip().lower()
    code = body.code.strip()
    auth_limiter.hit(f"register:email:{email}", limit=10, window_sec=600)

    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    _consume_register_challenge(db, email, code, purpose=PURPOSE_REGISTER)

    # 清理未完成验证的旧账号（若有）
    if existing:
        from app.services.member_sync import delete_user_with_member

        delete_user_with_member(db, existing)

    username = _gen_username(db)
    display_name = username
    user = User(
        username=username,
        email=email,
        display_name=display_name,
        password_hash=hash_password(body.password),
        role=UserRole.user,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    member = ensure_user_member(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    token = create_access_token(user.username, user_id=user.id)
    return RegisterResponse(
        message="注册成功",
        email=email,
        access_token=token,
    )


@router.post("/verify-email")
def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """兼容旧流程：已注册未验证用户补验证（验证码存于 register_challenges）。"""
    ip = client_ip(request)
    auth_limiter.hit(f"verify:ip:{ip}", limit=20, window_sec=600)

    email = str(body.email).strip().lower()
    code = body.code.strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="验证失败，请检查邮箱与验证码")
    if user.email_verified:
        return {"message": "邮箱已验证，可直接登录"}
    _consume_register_challenge(db, email, code, purpose=PURPOSE_REGISTER)
    user.email_verified = True
    db.commit()
    return {"message": "邮箱验证成功，请登录"}


@router.post("/resend-code", response_model=RegisterResponse)
def resend_code(
    body: ResendCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    email = str(body.email).strip().lower()
    auth_limiter.hit(f"resend:ip:{ip}", limit=10, window_sec=600)
    auth_limiter.hit(f"resend:email:{email}", limit=5, window_sec=600)

    user = db.query(User).filter(User.email == email).first()
    if not user or user.email_verified:
        return RegisterResponse(
            message="若需要验证，验证码已发送",
            email=email,
            delivery="skipped",
        )
    _, delivery = _upsert_register_challenge(db, email, purpose=PURPOSE_REGISTER)
    msg = "验证码已重新发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])
