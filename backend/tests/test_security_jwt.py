from datetime import timedelta

import jwt

from app.core.config import get_settings
from app.core.security import ALGORITHM, create_access_token, decode_access_token
from app.core.timeutil import utc_now


def test_new_token_uses_user_id_sub(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.auth_config.get_access_token_expire_minutes",
        lambda: 60,
    )
    token = create_access_token("alice", user_id=42)
    principal = decode_access_token(token)
    assert principal is not None
    assert principal.user_id == 42
    assert principal.username == "alice"


def test_legacy_username_sub_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "exp": utc_now() + timedelta(minutes=60),
            "sub": "bob",
            "username": "bob",
        },
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_invalid_token_returns_none() -> None:
    assert decode_access_token("not-a-jwt") is None
