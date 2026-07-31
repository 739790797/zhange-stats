from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.member_sync import ensure_user_member


def seed_data(db: Session) -> None:
    get_settings.cache_clear()
    settings = get_settings()
    admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
    if not admin:
        admin = User(
            username=settings.ADMIN_USERNAME,
            email=settings.ADMIN_EMAIL.lower(),
            display_name=settings.ADMIN_DISPLAY_NAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role=UserRole.admin,
            is_admin=True,
            email_verified=True,
        )
        db.add(admin)
        db.flush()
    else:
        # 已存在：只保证角色/展示信息，默认不重置密码（避免重启把弱口令写回）
        admin.apply_role(UserRole.admin)
        admin.display_name = settings.ADMIN_DISPLAY_NAME
        admin.email_verified = True
        desired_email = settings.ADMIN_EMAIL.lower()
        if admin.email != desired_email:
            taken = (
                db.query(User)
                .filter(User.email == desired_email, User.id != admin.id)
                .first()
            )
            if not taken:
                admin.email = desired_email
        if settings.RESET_ADMIN_PASSWORD:
            admin.password_hash = hash_password(settings.ADMIN_PASSWORD)

    if settings.ENFORCE_SINGLE_ADMIN:
        extras = (
            db.query(User)
            .filter(
                User.id != admin.id,
                (User.role == UserRole.admin) | (User.is_admin.is_(True)),
            )
            .all()
        )
        for u in extras:
            u.apply_role(UserRole.user)

    ensure_user_member(db, admin)
    db.commit()
