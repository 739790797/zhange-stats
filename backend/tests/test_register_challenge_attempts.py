"""邮箱验证码：错满次数即作废（计数随请求回滚也留得住）、重发清零、有效期封顶。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.auth.helpers import (
    MAX_CODE_ATTEMPTS,
    MAX_CODE_EXPIRE_MINUTES,
    PURPOSE_RESET,
    _consume_register_challenge,
    _upsert_register_challenge,
)
from app.core.database import Base
from app.core.timeutil import now_naive, to_naive
from app.models.member import Member  # noqa: F401
from app.models.register_challenge import RegisterChallenge
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.user import User  # noqa: F401

EMAIL = "user@example.com"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(
        "app.api.auth.helpers.send_verification_email",
        lambda *_a, **_k: {"sent": True, "mode": "log"},
    )
    yield session
    session.close()
    engine.dispose()


def _expire_minutes(monkeypatch, minutes: int) -> None:
    monkeypatch.setattr(
        "app.services.email_config.load_email_config",
        lambda _db: {"code_expire_minutes": minutes},
    )


def _row(db) -> RegisterChallenge | None:
    return (
        db.query(RegisterChallenge)
        .filter(RegisterChallenge.email == EMAIL, RegisterChallenge.purpose == PURPOSE_RESET)
        .first()
    )


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def _consume(db, code: str) -> HTTPException:
    with pytest.raises(HTTPException) as exc:
        _consume_register_challenge(db, EMAIL, code, purpose=PURPOSE_RESET)
    # 路由抛错后请求会话不提交；计数必须已经落库
    db.rollback()
    return exc.value


def test_wrong_codes_burn_the_challenge(db, monkeypatch) -> None:
    _expire_minutes(monkeypatch, 15)
    code, _ = _upsert_register_challenge(db, EMAIL, purpose=PURPOSE_RESET)
    assert _row(db).attempts == 0
    for n in range(1, MAX_CODE_ATTEMPTS):
        assert _consume(db, _wrong(code)).detail == "验证码错误"
        assert _row(db).attempts == n
    assert "次数过多" in _consume(db, _wrong(code)).detail
    assert _row(db) is None
    assert _consume(db, code).detail == "请先发送验证码"


def test_resend_resets_attempts(db, monkeypatch) -> None:
    _expire_minutes(monkeypatch, 15)
    code, _ = _upsert_register_challenge(db, EMAIL, purpose=PURPOSE_RESET)
    for _ in range(MAX_CODE_ATTEMPTS - 1):
        _consume(db, _wrong(code))
    fresh, _ = _upsert_register_challenge(db, EMAIL, purpose=PURPOSE_RESET)
    assert _row(db).attempts == 0
    _consume_register_challenge(db, EMAIL, fresh, purpose=PURPOSE_RESET)
    db.commit()
    assert _row(db) is None


def test_code_expiry_is_capped(db, monkeypatch) -> None:
    _expire_minutes(monkeypatch, 24 * 60)
    before = now_naive()
    _upsert_register_challenge(db, EMAIL, purpose=PURPOSE_RESET)
    expires = to_naive(_row(db).expires_at)
    assert expires <= before + timedelta(minutes=MAX_CODE_EXPIRE_MINUTES, seconds=5)
    assert expires >= before + timedelta(minutes=MAX_CODE_EXPIRE_MINUTES - 1)
