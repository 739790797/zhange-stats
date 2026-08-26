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
    """JWT 身份。新票 sub=user_id；旧票 sub=username。"""

    user_id: int | None
    username: str | None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    *,
    user_id: int | None = None,
) -> str:
    from app.services.auth_config import get_access_token_expire_minutes

    settings = get_settings()
    expire = utc_now() + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else get_access_token_expire_minutes()
    )
    payload: dict = {"exp": expire, "username": subject}
    if user_id is not None:
        payload["sub"] = str(int(user_id))
    else:
        payload["sub"] = subject
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> AccessPrincipal | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
    sub = payload.get("sub")
    username_claim = payload.get("username")
    username = str(username_claim) if username_claim else None
    if sub is None:
        return AccessPrincipal(user_id=None, username=username) if username else None
    text = str(sub)
    if text.isdigit():
        return AccessPrincipal(user_id=int(text), username=username or None)
    return AccessPrincipal(user_id=None, username=text)
