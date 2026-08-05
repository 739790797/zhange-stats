"""空库不再自动种子管理员；可选 ALLOW_ENV_ADMIN_SEED 供自动化。"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.auth_config import (
    enforce_single_admin_if_needed,
    get_min_password_length,
    load_auth_config,
)
from app.services.member_sync import ensure_user_member
from app.services.password_policy import PasswordPolicyError, validate_password
from app.services.setup import ensure_setup_marker_if_admins_exist, needs_setup


def seed_data(db: Session) -> None:
    get_settings.cache_clear()
    settings = get_settings()

    if not needs_setup(db):
        ensure_setup_marker_if_admins_exist(db)
        enforce_single_admin_if_needed(db)
        db.commit()
        return

    # 默认等待安装向导；仅显式开启时用 .env 种子（CI / 脚本）
    if not settings.ALLOW_ENV_ADMIN_SEED:
        return

    min_len = get_min_password_length(db)
    try:
        password = validate_password(
            settings.ADMIN_PASSWORD,
            username=settings.ADMIN_USERNAME,
            min_length=min_len,
        )
    except PasswordPolicyError as exc:
        from app.services.auth_config import effective_reject_weak_admin_password

        cfg = load_auth_config(db)
        if effective_reject_weak_admin_password(cfg):
            raise RuntimeError(
                f"无法创建种子管理员：{exc}。"
                "请设置更强的 ADMIN_PASSWORD，或关闭 ALLOW_ENV_ADMIN_SEED 改用安装向导。"
            ) from exc
        password = (settings.ADMIN_PASSWORD or "").strip() or "123456"

    admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
    if not admin:
        desired_email = settings.ADMIN_EMAIL.lower()
        email_taken = (
            db.query(User).filter(User.email == desired_email).first() is not None
        )
        admin = User(
            username=settings.ADMIN_USERNAME,
            email=None if email_taken else desired_email,
            display_name=settings.ADMIN_DISPLAY_NAME,
            password_hash=hash_password(password),
            role=UserRole.admin,
            email_verified=True,
        )
        db.add(admin)
        db.flush()
    else:
        admin.apply_role(UserRole.admin)
        admin.display_name = settings.ADMIN_DISPLAY_NAME or admin.display_name
        admin.email_verified = True

    ensure_user_member(db, admin)
    from app.services.setup import SETUP_COMPLETED_KEY
    from app.models.system_config import SystemConfig

    if db.get(SystemConfig, SETUP_COMPLETED_KEY) is None:
        db.add(SystemConfig(key=SETUP_COMPLETED_KEY, value="1"))
    enforce_single_admin_if_needed(db, keep_user_id=admin.id)
    db.commit()
