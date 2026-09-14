from dataclasses import dataclass
from datetime import timedelta

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.timeutil import utc_now

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


@dataclass(frozen=True)
class AccessPrincipal:
    """JWT 身份。`sub` 为 user_id。"""

    user_id: int
    username: str | None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    *,
    user_id: int,
) -> str:
    from app.services.auth_config import get_access_token_expire_minutes

    settings = get_settings()
    expire = utc_now() + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else get_access_token_expire_minutes()
    )
    payload: dict = {
        "exp": expire,
        "sub": str(int(user_id)),
        "username": subject,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> AccessPrincipal | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    text = str(sub)
    if not text.isdigit():
        return None
    username_claim = payload.get("username")
    username = str(username_claim) if username_claim else None
    return AccessPrincipal(user_id=int(text), username=username)
