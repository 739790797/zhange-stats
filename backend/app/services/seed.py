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
        admin.apply_role(UserRole.admin)
        admin.display_name = settings.ADMIN_DISPLAY_NAME
        admin.email = settings.ADMIN_EMAIL.lower()
        admin.email_verified = True
        admin.password_hash = hash_password(settings.ADMIN_PASSWORD)

    # 保证全局有且仅有一名管理员（种子账号）
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
