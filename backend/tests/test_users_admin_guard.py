"""管理端用户：显示名拒收尖括号；降级管理员加锁复核、至少留一名；改密 / 降级吊销对方旧会话。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request
from starlette.responses import Response

import app.models  # noqa: F401
from app.api.profile.users_admin import create_user, update_user
from app.core.database import Base
from app.core.security import DISPLAY_NAME_MARKUP_ERROR, hash_password
from app.core.timeutil import now_naive
from app.models.user import User, UserRole
from app.schemas import UserAdminCreate, UserAdminUpdate
from app.services.auth_config import admins_remaining, lock_admin_ids


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _user(db: Session, name: str, *, admin: bool = False) -> User:
    row = User(
        username=name,
        email=f"{name}@example.com",
        display_name=name,
        password_hash=hash_password("correct-horse-battery"),
        role=UserRole.admin if admin else UserRole.user,
        email_verified=True,
    )
    db.add(row)
    db.commit()
    return row


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "PATCH",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
    )


def _patch(db: Session, target: User, actor: User, **fields) -> None:
    update_user(
        target.id, UserAdminUpdate(**fields), _request(), Response(), db=db, current=actor
    )


def test_create_user_rejects_markup_in_display_name(db) -> None:
    root = _user(db, "root", admin=True)
    body = UserAdminCreate(
        email="new@example.com",
        display_name="<img src=x onerror=alert(1)>",
        password="Str0ng-Enough!",
    )
    with pytest.raises(HTTPException) as exc:
        create_user(body, db=db, _=root)
    assert exc.value.status_code == 400
    assert exc.value.detail == DISPLAY_NAME_MARKUP_ERROR
    assert db.query(User).count() == 1


def test_update_user_rejects_markup_in_display_name(db) -> None:
    root = _user(db, "root", admin=True)
    bob = _user(db, "bob")
    with pytest.raises(HTTPException) as exc:
        _patch(db, bob, root, display_name="bob<script>")
    assert exc.value.detail == DISPLAY_NAME_MARKUP_ERROR
    db.rollback()
    assert db.get(User, bob.id).display_name == "bob"


def test_demotion_revokes_sessions(db) -> None:
    root = _user(db, "root", admin=True)
    other = _user(db, "other", admin=True)
    _patch(db, other, root, role="user")
    db.refresh(other)
    assert other.role == UserRole.user
    assert other.token_version == 1


def test_cross_demotion_race_leaves_an_admin(db) -> None:
    a = _user(db, "a", admin=True)
    b = _user(db, "b", admin=True)
    # 另一笔请求（B 降 A）已提交；A 这笔在那之前就过了 require_admin
    db.query(User).filter(User.id == a.id).update({User.role: UserRole.user})
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _patch(db, b, a, role="user")
    assert exc.value.detail == "系统至少保留一名管理员"
    db.rollback()
    assert db.get(User, b.id).role == UserRole.admin


def test_admin_password_reset_revokes_target_sessions(db) -> None:
    root = _user(db, "root", admin=True)
    bob = _user(db, "bob")
    _patch(db, bob, root, password="Fresh-Passw0rd!")
    db.refresh(bob)
    assert bob.token_version == 1
    db.refresh(root)
    assert root.token_version == 0


def test_anonymized_admins_do_not_count(db) -> None:
    ghost = _user(db, "ghost", admin=True)
    ghost.anonymized_at = now_naive()
    root = _user(db, "root", admin=True)
    db.commit()
    assert lock_admin_ids(db) == [root.id]
    assert admins_remaining(db) == 1
