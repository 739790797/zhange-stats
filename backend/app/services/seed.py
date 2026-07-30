from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.game import Game
from app.models.user import User


def seed_data(db: Session) -> None:
    settings = get_settings()
    admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
    if not admin:
        admin = User(
            username=settings.ADMIN_USERNAME,
            display_name=settings.ADMIN_DISPLAY_NAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            is_admin=True,
        )
        db.add(admin)

    seed_games = [
        ("王者荣耀", "手游"),
        ("CS2", "Steam"),
    ]
    for name, platform in seed_games:
        exists = db.query(Game).filter(Game.name == name).first()
        if not exists:
            db.add(Game(name=name, platform=platform))

    db.commit()
