from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest

from app.core.config import get_settings
from app.core.key_derivation import PURPOSE_JWT, derive_key
from app.core.security import (
    ALGORITHM,
    MAX_ACCESS_TOKEN_MINUTES,
    AccessPrincipal,
    bump_token_version,
    create_access_token,
    decode_access_token,
    token_version_matches,
)
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


def _jwt_key() -> bytes:
    return derive_key(get_settings().SECRET_KEY, PURPOSE_JWT)


def test_token_signed_with_derived_key_and_carries_version() -> None:
    token = create_access_token("alice", user_id=7, token_version=3)
    payload = jwt.decode(token, _jwt_key(), algorithms=[ALGORITHM])
    assert payload["ver"] == 3
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, get_settings().SECRET_KEY, algorithms=[ALGORITHM])
    principal = decode_access_token(token)
    assert principal is not None
    assert principal.token_version == 3


def test_expiry_clamped_to_thirty_days() -> None:
    token = create_access_token("alice", 60 * 24 * 365, user_id=7)
    payload = jwt.decode(token, _jwt_key(), algorithms=[ALGORITHM])
    assert payload["exp"] - utc_now().timestamp() <= MAX_ACCESS_TOKEN_MINUTES * 60 + 5


def _raw_key_token(minutes: int) -> str:
    return jwt.encode(
        {"exp": utc_now() + timedelta(minutes=minutes), "sub": "5", "username": "carol"},
        get_settings().SECRET_KEY,
        algorithm=ALGORITHM,
    )


def test_pre_upgrade_token_accepted_within_new_max() -> None:
    principal = decode_access_token(_raw_key_token(60))
    assert principal is not None
    assert principal.user_id == 5
    assert principal.token_version is None


def test_pre_upgrade_token_beyond_new_max_rejected() -> None:
    assert decode_access_token(_raw_key_token(MAX_ACCESS_TOKEN_MINUTES + 60)) is None


@pytest.mark.parametrize("ver", ["1", True, 1.0, None])
def test_non_integer_version_rejected(ver) -> None:
    token = jwt.encode(
        {"exp": utc_now() + timedelta(minutes=5), "sub": "5", "ver": ver},
        _jwt_key(),
        algorithm=ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_token_version_must_match_user() -> None:
    user = SimpleNamespace(token_version=0)
    assert token_version_matches(AccessPrincipal(1, "a", None), user)
    assert token_version_matches(AccessPrincipal(1, "a", 0), user)
    assert bump_token_version(user) == 1
    assert not token_version_matches(AccessPrincipal(1, "a", None), user)
    assert not token_version_matches(AccessPrincipal(1, "a", 0), user)
    assert token_version_matches(AccessPrincipal(1, "a", 1), user)
