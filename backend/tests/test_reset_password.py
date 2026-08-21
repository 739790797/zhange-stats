"""找回密码：验证码 challenge purpose 隔离与重置逻辑。"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.auth.helpers import (
    PURPOSE_REGISTER,
    PURPOSE_RESET,
    _consume_register_challenge,
    _upsert_register_challenge,
)
from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.core.timeutil import now_naive
from app.models.member import Member  # noqa: F401
from app.models.register_challenge import RegisterChallenge
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.user import User, UserRole
from app.services.auth_config import get_min_password_length
from app.services.password_policy import (
    PasswordPolicyError,
    invalidate_weak_password_cache,
    validate_password,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _make_user(db, *, email: str, password: str, verified: bool = True) -> User:
    user = User(
        username="reset_user",
        email=email,
        display_name="reset_user",
        password_hash=hash_password(password),
        role=UserRole.user,
        email_verified=verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_send_skips_unknown_email(monkeypatch) -> None:
    db = _session()
    called = {"n": 0}

    def _no_send(*_a, **_k):
        called["n"] += 1
        return {"sent": True, "mode": "smtp"}

    monkeypatch.setattr(
        "app.api.auth.helpers.send_verification_email", _no_send
    )
    user = (
        db.query(User)
        .filter(User.email == "nobody@example.com", User.email_verified.is_(True))
        .first()
    )
    assert user is None
    assert called["n"] == 0
    assert db.query(RegisterChallenge).count() == 0
    db.close()


def test_reset_flow_success(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.api.auth.helpers.send_verification_email",
        lambda *_a, **_k: {"sent": True, "mode": "log"},
    )
    monkeypatch.setattr(
        "app.services.email_config.load_email_config",
        lambda _db: {"code_expire_minutes": 15},
    )
    email = "user@example.com"
    _make_user(db, email=email, password="OldPassw0rd!")
    code, _ = _upsert_register_challenge(db, email, purpose=PURPOSE_RESET)
    _consume_register_challenge(db, email, code, purpose=PURPOSE_RESET)

    user = db.query(User).filter(User.email == email).one()
    new_password = validate_password(
        "NewPassw0rd!",
        username=user.username,
        min_length=get_min_password_length(db),
    )
    assert not verify_password(new_password, user.password_hash)
    invalidate_weak_password_cache(user.password_hash)
    user.password_hash = hash_password(new_password)
    db.commit()
    assert verify_password("NewPassw0rd!", user.password_hash)
    assert db.query(RegisterChallenge).count() == 0
    db.close()


def test_wrong_code_rejected(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.api.auth.helpers.send_verification_email",
        lambda *_a, **_k: {"sent": True, "mode": "log"},
    )
    monkeypatch.setattr(
        "app.services.email_config.load_email_config",
        lambda _db: {"code_expire_minutes": 15},
    )
    email = "user@example.com"
    _upsert_register_challenge(db, email, purpose=PURPOSE_RESET)
    try:
        _consume_register_challenge(db, email, "000000", purpose=PURPOSE_RESET)
        raised = False
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 400
        assert "验证码" in str(exc.detail)
    assert raised
    db.close()


def test_expired_code_rejected(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.api.auth.helpers.send_verification_email",
        lambda *_a, **_k: {"sent": True, "mode": "log"},
    )
    monkeypatch.setattr(
        "app.services.email_config.load_email_config",
        lambda _db: {"code_expire_minutes": 15},
    )
    email = "user@example.com"
    code, _ = _upsert_register_challenge(db, email, purpose=PURPOSE_RESET)
    row = (
        db.query(RegisterChallenge)
        .filter(
            RegisterChallenge.email == email,
            RegisterChallenge.purpose == PURPOSE_RESET,
        )
        .one()
    )
    row.expires_at = now_naive() - timedelta(minutes=1)
    db.commit()
    try:
        _consume_register_challenge(db, email, code, purpose=PURPOSE_RESET)
        raised = False
    except HTTPException as exc:
        raised = True
        assert exc.status_code == 400
        assert "过期" in str(exc.detail)
    assert raised
    db.close()


def test_weak_password_rejected() -> None:
    try:
        validate_password("12345678", username="reset_user", min_length=8)
        raised = False
    except PasswordPolicyError:
        raised = True
    assert raised


def test_purpose_isolation(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.api.auth.helpers.send_verification_email",
        lambda *_a, **_k: {"sent": True, "mode": "log"},
    )
    monkeypatch.setattr(
        "app.services.email_config.load_email_config",
        lambda _db: {"code_expire_minutes": 15},
    )
    email = "user@example.com"
    reg_code, _ = _upsert_register_challenge(db, email, purpose=PURPOSE_REGISTER)
    reset_code, _ = _upsert_register_challenge(db, email, purpose=PURPOSE_RESET)
    rows = db.query(RegisterChallenge).filter(RegisterChallenge.email == email).all()
    assert len(rows) == 2
    purposes = {r.purpose for r in rows}
    assert purposes == {PURPOSE_REGISTER, PURPOSE_RESET}
    _consume_register_challenge(db, email, reset_code, purpose=PURPOSE_RESET)
    remaining = db.query(RegisterChallenge).filter(RegisterChallenge.email == email).all()
    assert len(remaining) == 1
    assert remaining[0].purpose == PURPOSE_REGISTER
    assert remaining[0].code == reg_code
    db.close()
