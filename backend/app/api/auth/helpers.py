from __future__ import annotations

import hmac
import secrets
import string
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.schemas import UserOut
from app.services.email import send_verification_email

PURPOSE_REGISTER = "register"
PURPOSE_BIND = "bind"
PURPOSE_RESET = "reset"


def _utcnow() -> datetime:
    return now_naive()


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


def _upsert_register_challenge(
    db: Session,
    email: str,
    *,
    purpose: str = PURPOSE_REGISTER,
) -> tuple[str, dict]:
    from app.services.email_config import load_email_config

    cfg = load_email_config(db)
    expire_minutes = max(1, int(cfg.get("code_expire_minutes") or 15))
    code = _gen_code()
    expires = _utcnow() + timedelta(minutes=expire_minutes)
    row = (
        db.query(RegisterChallenge)
        .filter(
            RegisterChallenge.email == email,
            RegisterChallenge.purpose == purpose,
        )
        .first()
    )
    if row:
        row.code = code
        row.expires_at = expires
    else:
        db.add(
            RegisterChallenge(
                email=email,
                purpose=purpose,
                code=code,
                expires_at=expires,
            )
        )
    db.commit()
    delivery = send_verification_email(email, code, db=db, purpose=purpose)
    if delivery.get("mode") == "unavailable":
        row = (
            db.query(RegisterChallenge)
            .filter(
                RegisterChallenge.email == email,
                RegisterChallenge.purpose == purpose,
            )
            .first()
        )
        if row:
            db.delete(row)
            db.commit()
        raise HTTPException(
            status_code=503,
            detail="邮件服务未配置，无法发送验证码。请配置 SMTP，或本地调试时设置 ALLOW_EMAIL_CODE_LOG=true",
        )
    return code, delivery


def _consume_register_challenge(
    db: Session,
    email: str,
    code: str,
    *,
    purpose: str = PURPOSE_REGISTER,
) -> None:
    row = (
        db.query(RegisterChallenge)
        .filter(
            RegisterChallenge.email == email,
            RegisterChallenge.purpose == purpose,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="请先发送验证码")
    if to_naive(row.expires_at) < _utcnow():
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
        is_admin=user.is_admin_user,
        email_verified=bool(user.email_verified),
        avatar_url=member.avatar_url if member else None,
        steam_id=member.steam_id if member else None,
        created_at=user.created_at,
    )
