"""显示名拒收 `<` `>`：前端漏转义的地方（Leaflet tooltip 等）不至于成为存储型 XSS。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.api.profile.helpers import _apply_profile_fields, _set_qq_profile
from app.core.database import Base
from app.core.security import (
    DISPLAY_NAME_MARKUP_ERROR,
    has_markup_chars,
    hash_password,
    strip_markup_chars,
)
from app.models.member import Member
from app.models.user import User, UserRole


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _user_with_member(db) -> tuple[User, Member]:
    user = User(
        username="alice",
        email="alice@example.com",
        display_name="alice",
        password_hash=hash_password("correct-horse-battery"),
        role=UserRole.user,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    member = Member(nickname="alice", user_id=user.id)
    db.add(member)
    db.commit()
    return user, member


def test_markup_helpers() -> None:
    assert has_markup_chars("a<b")
    assert has_markup_chars("x>")
    assert not has_markup_chars("Tom & Jerry \"'")
    assert not has_markup_chars(None)
    assert strip_markup_chars("<img src=x>小明") == "img src=x小明"
    assert strip_markup_chars(None) == ""


@pytest.mark.parametrize("name", ["<b>bold</b>", "a>b", "<img src=x onerror=alert(1)>"])
def test_profile_rejects_markup(db, name: str) -> None:
    user, member = _user_with_member(db)
    with pytest.raises(HTTPException) as exc:
        _apply_profile_fields(db, user, member, {"display_name": name})
    assert exc.value.status_code == 400
    assert exc.value.detail == DISPLAY_NAME_MARKUP_ERROR
    assert user.display_name == "alice"


def test_profile_keeps_other_punctuation(db) -> None:
    user, member = _user_with_member(db)
    _apply_profile_fields(db, user, member, {"display_name": "  Tom & Jerry's \"队\"  "})
    assert user.display_name == "Tom & Jerry's \"队\""
    assert member.nickname == user.display_name


def test_qq_nickname_is_stripped_not_rejected(db) -> None:
    _user, member = _user_with_member(db)
    nick = _set_qq_profile(db, member, openid="openid-1", nickname=" <img src=x>小明 ")
    assert nick == "img src=x小明"
    assert member.qq_nickname == nick
    assert _set_qq_profile(db, member, openid="openid-1", nickname="<>") is None
