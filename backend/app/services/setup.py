"""首次安装：无管理员时走向导创建首位管理员。"""

from __future__ import annotations

import secrets
import string

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.system_config import SystemConfig
from app.models.user import User, UserRole
from app.services.auth_config import get_min_password_length
from app.services.member_sync import ensure_user_member
from app.services.password_policy import PasswordPolicyError, validate_password

SETUP_COMPLETED_KEY = "setup_completed"


class SetupError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def needs_setup(db: Session) -> bool:
    return db.query(User).filter(User.role == UserRole.admin).count() == 0


def ensure_setup_marker_if_admins_exist(db: Session) -> None:
    """已有管理员的旧库：补写完成标记。"""
    if needs_setup(db):
        return
    row = db.get(SystemConfig, SETUP_COMPLETED_KEY)
    if row is None:
        db.add(SystemConfig(key=SETUP_COMPLETED_KEY, value="1"))
        db.commit()


def _unique_username(db: Session) -> str:
    alphabet = string.ascii_lowercase + string.digits
    for _ in range(20):
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        username = f"admin_{suffix}"
        if not db.query(User).filter(User.username == username).first():
            return username
    raise SetupError("无法生成唯一用户名，请重试", status_code=500)


def complete_initial_admin(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
) -> tuple[User, str]:
    """创建首位管理员并返回 (user, access_token)。"""
    if not needs_setup(db):
        raise SetupError("系统已完成初始化", status_code=409)

    email_norm = email.strip().lower()
    name = display_name.strip()
    if not name:
        raise SetupError("请填写显示名")
    if "@" not in email_norm:
        raise SetupError("邮箱格式不正确")

    if db.query(User).filter(User.email == email_norm).first():
        raise SetupError("该邮箱已被使用")

    try:
        password_ok = validate_password(
            password,
            min_length=get_min_password_length(db),
        )
    except PasswordPolicyError as exc:
        raise SetupError(str(exc)) from exc

    user = User(
        username=_unique_username(db),
        email=email_norm,
        display_name=name[:64],
        password_hash=hash_password(password_ok),
        role=UserRole.admin,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    # 极窄竞态：若已有其他管理员，撤销本次创建
    others = (
        db.query(User)
        .filter(User.role == UserRole.admin, User.id != user.id)
        .count()
    )
    if others > 0:
        db.rollback()
        raise SetupError("系统已完成初始化", status_code=409)

    ensure_user_member(db, user)
    if db.get(SystemConfig, SETUP_COMPLETED_KEY) is None:
        db.add(SystemConfig(key=SETUP_COMPLETED_KEY, value="1"))
    db.commit()
    db.refresh(user)
    token = create_access_token(user.username)
    return user, token
