from __future__ import annotations

import hmac
import secrets
import string
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.schemas import UserOut
from app.services.email import (
    precheck_email_delivery,
    send_notice_email,
    send_verification_email,
)
from app.services.email_config import code_expire_minutes

PURPOSE_REGISTER = "register"
PURPOSE_BIND = "bind"
PURPOSE_RESET = "reset"
PURPOSE_DELETE = "delete"
PURPOSE_STEPUP = "admin_stepup"

# 6 位数字码：可试次数与有效期上限（email_config.MAX_CODE_EXPIRE_MINUTES）共同决定猜中概率
MAX_CODE_ATTEMPTS = 5

_DELIVERY_ERRORS = {
    "smtp_error": "邮件发送失败，请稍后重试",
    "unavailable": (
        "邮件服务未配置，无法发送验证码。请配置 SMTP，或本地调试时设置 ALLOW_EMAIL_CODE_LOG=true"
    ),
}


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


def _require_email_delivery(db: Session) -> None:
    """查邮箱是否已注册之前先确认邮件发得出去：已注册与未注册邮箱拿到同样的 503。"""
    from app.services.email_config import load_email_config

    mode = precheck_email_delivery(load_email_config(db))
    if mode in _DELIVERY_ERRORS:
        raise HTTPException(status_code=503, detail=_DELIVERY_ERRORS[mode])


def _upsert_register_challenge(
    db: Session,
    email: str,
    *,
    purpose: str = PURPOSE_REGISTER,
    notice: str | None = None,
) -> tuple[str, dict]:
    """写入新验证码并发信。

    给了 notice（如邮箱已注册）时照样落一条码，但发的是不带码的提醒信：
    之后拿任意码来试，得到的报错与正常邮箱输错码完全一样。
    """
    from app.services.email_config import load_email_config

    cfg = load_email_config(db)
    code = _gen_code()
    expires = now_naive() + timedelta(minutes=code_expire_minutes(cfg))
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
        row.attempts = 0
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
    if notice:
        delivery = send_notice_email(email, notice, db=db)
    else:
        delivery = send_verification_email(email, code, db=db, purpose=purpose)
    mode = delivery.get("mode")
    if mode in _DELIVERY_ERRORS:
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
        raise HTTPException(status_code=503, detail=_DELIVERY_ERRORS[mode])
    return code, delivery


def _delete_challenges_for_email(db: Session, email: str) -> None:
    ident = (email or "").strip().lower()
    if not ident:
        return
    (
        db.query(RegisterChallenge)
        .filter(RegisterChallenge.email == ident)
        .delete(synchronize_session=False)
    )


def _delivery_user_message(delivery: dict, *, sent: str, logged: str) -> str:
    if delivery.get("mode") == "log":
        return logged
    return sent


def _consume_register_challenge(
    db: Session,
    email: str,
    code: str,
    *,
    purpose: str = PURPOSE_REGISTER,
) -> None:
    """校验并删除验证码。码错时失败计数会立即提交，调用前不要留未提交的写入。"""
    challenge = (
        RegisterChallenge.email == email,
        RegisterChallenge.purpose == purpose,
    )
    row = db.query(RegisterChallenge).filter(*challenge).first()
    if not row:
        raise HTTPException(status_code=400, detail="请先发送验证码")
    if to_naive(row.expires_at) < now_naive():
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")
    provided = code.strip()
    if len(provided) != len(row.code) or not hmac.compare_digest(row.code, provided):
        # 原子自增：并发猜码不会因读-改-写丢计数
        db.query(RegisterChallenge).filter(*challenge).update(
            {RegisterChallenge.attempts: RegisterChallenge.attempts + 1},
            synchronize_session=False,
        )
        attempts = (
            db.query(RegisterChallenge.attempts).filter(*challenge).scalar() or 0
        )
        exhausted = attempts >= MAX_CODE_ATTEMPTS
        if exhausted:
            db.query(RegisterChallenge).filter(*challenge).delete(
                synchronize_session=False
            )
        db.commit()
        if exhausted:
            raise HTTPException(
                status_code=400, detail="验证码错误次数过多，请重新获取"
            )
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
