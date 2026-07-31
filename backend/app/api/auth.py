from __future__ import annotations

import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import auth_limiter, client_ip
from app.core.security import create_access_token, hash_password, verify_password
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.services.email import send_verification_email
from app.services.member_sync import ensure_user_member

router = APIRouter(prefix="/auth", tags=["auth"])


class SendRegisterCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    code: str = Field(min_length=4, max_length=16)


class RegisterResponse(BaseModel):
    message: str
    email: str
    delivery: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class ResendCodeRequest(BaseModel):
    email: EmailStr


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _gen_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _gen_username(db: Session) -> str:
    alphabet = string.ascii_lowercase + string.digits
    for _ in range(20):
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        username = f"user_{suffix}"
        if not db.query(User).filter(User.username == username).first():
            return username
    raise HTTPException(status_code=500, detail="无法生成唯一用户名，请重试")


def _upsert_register_challenge(db: Session, email: str) -> tuple[str, dict]:
    settings = get_settings()
    code = _gen_code()
    expires = _utcnow() + timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES)
    row = db.query(RegisterChallenge).filter(RegisterChallenge.email == email).first()
    if row:
        row.code = code
        row.expires_at = expires
    else:
        db.add(RegisterChallenge(email=email, code=code, expires_at=expires))
    db.commit()
    delivery = send_verification_email(email, code, db=db)
    return code, delivery


def _consume_register_challenge(db: Session, email: str, code: str) -> None:
    row = db.query(RegisterChallenge).filter(RegisterChallenge.email == email).first()
    if not row:
        raise HTTPException(status_code=400, detail="请先发送验证码")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    provided = code.strip()
    if len(provided) != len(row.code) or not hmac.compare_digest(row.code, provided):
        raise HTTPException(status_code=400, detail="验证码错误")
    db.delete(row)
    db.flush()


def _user_out(user: User) -> UserOut:
    member = user.member
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value if isinstance(user.role, UserRole) else str(user.role),
        is_admin=bool(user.is_admin) or user.role == UserRole.admin,
        email_verified=bool(user.email_verified),
        avatar_url=member.avatar_url if member else None,
        steam_id=member.steam_id if member else None,
        created_at=user.created_at,
    )


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
    _, delivery = _upsert_register_challenge(db, email)
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

    _consume_register_challenge(db, email, code)

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
        is_admin=False,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    member = ensure_user_member(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    token = create_access_token(user.username)
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
    _consume_register_challenge(db, email, code)
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
    _, delivery = _upsert_register_challenge(db, email)
    msg = "验证码已重新发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


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
    token = create_access_token(user.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    member = ensure_user_member(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(member)
    user.member = member
    return _user_out(user)
