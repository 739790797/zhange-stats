from datetime import datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest

from app.core.config import get_settings
from app.core.key_derivation import PURPOSE_JWT, derive_key
from app.core.security import (
    ALGORITHM,
    MAX_ACCESS_TOKEN_MINUTES,
    TOKEN_CLOCK_SKEW_SEC,
    AccessPrincipal,
    bump_token_version,
    create_access_token,
    decode_access_token,
    token_issued_after_user_created,
    token_version_matches,
)
from app.core.timeutil import UTC, ensure, utc_now


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


@pytest.mark.parametrize("minutes", [60, MAX_ACCESS_TOKEN_MINUTES + 60])
def test_pre_upgrade_raw_key_token_rejected(minutes) -> None:
    token = jwt.encode(
        {"exp": utc_now() + timedelta(minutes=minutes), "sub": "5", "username": "carol"},
        get_settings().SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert decode_access_token(token) is None


def _derived_key_token(**claims) -> str:
    payload = {"exp": utc_now() + timedelta(minutes=5), "sub": "5", "ver": 0, **claims}
    return jwt.encode(payload, _jwt_key(), algorithm=ALGORITHM)


@pytest.mark.parametrize("ver", ["1", True, 1.0, None])
def test_non_integer_version_rejected(ver) -> None:
    assert decode_access_token(_derived_key_token(iat=utc_now(), ver=ver)) is None


def test_token_carries_integer_issued_at() -> None:
    before = int(utc_now().timestamp())
    token = create_access_token("alice", user_id=7)
    payload = jwt.decode(token, _jwt_key(), algorithms=[ALGORITHM])
    assert isinstance(payload["iat"], int)
    assert before <= payload["iat"] <= int(utc_now().timestamp())
    principal = decode_access_token(token)
    assert principal is not None
    assert principal.issued_at == payload["iat"]


def test_token_without_issued_at_rejected() -> None:
    assert decode_access_token(_derived_key_token(iat=utc_now())) is not None
    assert decode_access_token(_derived_key_token()) is None


@pytest.mark.parametrize("iat", ["1700000000", True, 1700000000.5])
def test_non_integer_issued_at_rejected(iat) -> None:
    assert decode_access_token(_derived_key_token(iat=iat)) is None


def test_issued_at_from_a_slightly_fast_clock_accepted() -> None:
    now = int(utc_now().timestamp())
    assert decode_access_token(_derived_key_token(iat=now + TOKEN_CLOCK_SKEW_SEC - 2)) is not None
    assert decode_access_token(_derived_key_token(iat=now + 60)) is None


def test_token_issued_before_the_account_existed_rejected() -> None:
    created = datetime(2026, 10, 10, 12, 0, 0, 600000)
    created_ts = int(ensure(created).timestamp())
    user = SimpleNamespace(created_at=created)

    def issued(at: int | None) -> bool:
        return token_issued_after_user_created(AccessPrincipal(1, "a", 0, at), user)

    assert issued(created_ts + 3600)
    # 同一请求里建号再签发：iat 截成整秒、MySQL 还会把毫秒进位
    assert issued(created_ts)
    assert issued(created_ts - TOKEN_CLOCK_SKEW_SEC + 1)
    assert not issued(created_ts - TOKEN_CLOCK_SKEW_SEC - 1)
    assert not issued(created_ts - 3600)
    assert not issued(None)
    aware = SimpleNamespace(created_at=ensure(created).astimezone(UTC))
    assert token_issued_after_user_created(AccessPrincipal(1, "a", 0, created_ts), aware)


def test_token_version_must_match_user() -> None:
    user = SimpleNamespace(token_version=0)
    assert token_version_matches(AccessPrincipal(1, "a", None), user)
    assert token_version_matches(AccessPrincipal(1, "a", 0), user)
    assert bump_token_version(user) == 1
    assert not token_version_matches(AccessPrincipal(1, "a", None), user)
    assert not token_version_matches(AccessPrincipal(1, "a", 0), user)
    assert token_version_matches(AccessPrincipal(1, "a", 1), user)
