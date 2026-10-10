"""ALLOW_ENV_ADMIN_SEED 种子管理员：ADMIN_PASSWORD 去掉首尾空白再校验、再存，尾随换行不会变成打不出来的口令。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base
from app.core.security import verify_login_password, verify_password
from app.models.user import User, UserRole
from app.services.seed import seed_data


@pytest.fixture
def db(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("REJECT_WEAK_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ALLOW_ENV_ADMIN_SEED", "true")
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("ADMIN_EMAIL", "root@example.com")
    monkeypatch.setattr("app.services.seed._seed_tavern_content", lambda _db: None)
    get_settings.cache_clear()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()
    get_settings.cache_clear()


@pytest.mark.parametrize("raw", ["Str0ng-Enough!\n", "Str0ng-Enough!\r\n", "  Str0ng-Enough!\t"])
def test_seed_password_is_stored_without_surrounding_whitespace(db, monkeypatch, raw: str) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", raw)
    get_settings.cache_clear()
    seed_data(db)
    admin = db.query(User).filter(User.username == "root").one()
    assert admin.role == UserRole.admin
    assert verify_password("Str0ng-Enough!", admin.password_hash)
    assert not verify_password(raw, admin.password_hash)
    assert verify_login_password("Str0ng-Enough!", admin.password_hash)


def test_weak_seed_password_is_refused_in_production_even_when_padded(db, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", " 123456\n")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="无法创建种子管理员"):
        seed_data(db)
    assert db.query(User).count() == 0
