from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
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
    password: str = Field(min_length=6, max_length=72)
    code: str = Field(min_length=4, max_length=16)


class RegisterResponse(BaseModel):
    message: str
    email: str
    delivery: str | None = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=16)


class ResendCodeRequest(BaseModel):
    email: EmailStr


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _gen_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def _gen_username(db: Session) -> str:
    for _ in range(20):
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        username = f"user_{suffix}"
        if not db.query(User).filter(User.username == username).first():
            return username
    raise HTTPException(status_code=500, detail="无法生成唯一用户名，请重试")


def _set_user_verify_code(user: User) -> str:
    settings = get_settings()
    code = _gen_code()
    user.verify_code = code
    user.verify_code_expires_at = _utcnow() + timedelta(
        minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
    )
    return code


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
    if row.code != code.strip():
        raise HTTPException(status_code=400, detail="验证码错误")
    db.delete(row)
    db.flush()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value if isinstance(user.role, UserRole) else str(user.role),
        is_admin=bool(user.is_admin) or user.role == UserRole.admin,
        email_verified=bool(user.email_verified),
        created_at=user.created_at,
    )


@router.post("/send-register-code", response_model=RegisterResponse)
def send_register_code(
    body: SendRegisterCodeRequest, db: Session = Depends(get_db)
) -> RegisterResponse:
    email = str(body.email).strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.email_verified:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    # 未验证完的旧账号：允许重新发码并在注册时覆盖创建
    _, delivery = _upsert_register_challenge(db, email)
    msg = "验证码已发送，请查收邮箱"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志（邮件未配置或发送失败）"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    email = str(body.email).strip().lower()
    code = body.code.strip()

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
    ensure_user_member(db, user)
    db.commit()

    return RegisterResponse(message="注册成功，请登录", email=email)


@router.post("/verify-email")
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict:
    """兼容旧流程：已注册未验证用户补验证。"""
    email = str(body.email).strip().lower()
    code = body.code.strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.email_verified:
        return {"message": "邮箱已验证，可直接登录"}
    if not user.verify_code or not user.verify_code_expires_at:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    expires = user.verify_code_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    if user.verify_code != code:
        raise HTTPException(status_code=400, detail="验证码错误")

    user.email_verified = True
    user.verify_code = None
    user.verify_code_expires_at = None
    db.commit()
    return {"message": "邮箱验证成功，请登录"}


@router.post("/resend-code", response_model=RegisterResponse)
def resend_code(
    body: ResendCodeRequest, db: Session = Depends(get_db)
) -> RegisterResponse:
    email = str(body.email).strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="邮箱已验证")
    code = _set_user_verify_code(user)
    db.commit()
    delivery = send_verification_email(email, code, db=db)
    msg = "验证码已重新发送"
    if delivery["mode"] == "log":
        msg = "验证码已输出到服务端日志"
    return RegisterResponse(message=msg, email=email, delivery=delivery["mode"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    account = body.username.strip()
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
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
