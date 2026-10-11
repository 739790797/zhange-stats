from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.auth.helpers import (
    PURPOSE_REGISTER,
    _consume_register_challenge,
    _delete_challenges_for_email,
    _delivery_user_message,
    _gen_username,
    _require_email_delivery,
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
from app.core.security import hash_password
from app.core.session_cookies import issue_session
from app.models.user import User, UserRole
from app.services.auth_config import get_min_password_length
from app.services.email import NOTICE_ALREADY_REGISTERED
from app.services.member_sync import ensure_user_member
from app.services.password_policy import PasswordPolicyError, validate_password

router = APIRouter()


def _send_register_code_or_notice(db: Session, email: str) -> dict:
    """已注册邮箱收到「已有账号」提醒而不是验证码；接口响应与未注册邮箱完全一样。"""
    _require_email_delivery(db)
    existing = db.query(User).filter(User.email == email).first()
    notice = NOTICE_ALREADY_REGISTERED if existing and existing.email_verified else None
    _, delivery = _upsert_register_challenge(
        db, email, purpose=PURPOSE_REGISTER, notice=notice
    )
    return delivery


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

    delivery = _send_register_code_or_notice(db, email)
    msg = _delivery_user_message(
        delivery,
        sent="若该邮箱可注册，验证码已发送",
        logged="验证码已输出到服务端日志（邮件未配置）",
    )
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/register", response_model=RegisterResponse)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    ip = client_ip(request)
    auth_limiter.hit(f"register:ip:{ip}", limit=10, window_sec=600)

    email = str(body.email).strip().lower()
    code = body.code.strip()
    auth_limiter.hit(f"register:email:{email}", limit=10, window_sec=600)

    try:
        password = validate_password(
            body.password, min_length=get_min_password_length(db)
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 先验码再查邮箱：没有验证码的人分不出邮箱是否已注册
    _consume_register_challenge(db, email, code, purpose=PURPOSE_REGISTER)
    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        db.commit()
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    _delete_challenges_for_email(db, email)

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
        password_hash=hash_password(password),
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
    issue_session(response, request, user)
    return RegisterResponse(message="注册成功", email=email)


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
    auth_limiter.hit(f"verify:email:{email}", limit=10, window_sec=600)
    _consume_register_challenge(db, email, code, purpose=PURPOSE_REGISTER)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        # 码是发给新邮箱注册用的：回滚不消耗，留给 /register
        db.rollback()
        raise HTTPException(status_code=400, detail="验证失败，请检查邮箱与验证码")
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

    delivery = _send_register_code_or_notice(db, email)
    msg = _delivery_user_message(
        delivery,
        sent="若需要验证，验证码已发送",
        logged="验证码已输出到服务端日志",
    )
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])
