"""安装向导：无管理员时创建首位管理员；安装令牌只落盘不进日志。"""

import logging
import stat

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from app.core.security import verify_password
from app.models.system_config import SystemConfig
from app.models.user import User, UserRole
from app.models.member import Member  # noqa: F401
from app.services.setup import (
    SETUP_COMPLETED_KEY,
    SetupError,
    complete_initial_admin,
    delete_setup_token,
    ensure_setup_token,
    is_setup_complete_cached,
    mark_setup_complete,
    needs_setup,
    read_setup_token,
    reset_setup_complete_for_tests,
    setup_open,
    setup_token_matches,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_needs_setup_empty() -> None:
    db = _session()
    assert needs_setup(db) is True
    db.close()


def test_complete_initial_admin(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.services.setup.get_min_password_length", lambda _db: 8
    )
    monkeypatch.setattr(
        "app.services.setup.create_user_access_token", lambda _u: "tok"
    )

    user, token = complete_initial_admin(
        db,
        email="admin@example.com",
        display_name="站长",
        password="Str0ng-Enough!",
    )
    assert token == "tok"
    assert user.role == UserRole.admin
    assert user.email == "admin@example.com"
    assert verify_password("Str0ng-Enough!", user.password_hash)
    assert needs_setup(db) is False

    try:
        complete_initial_admin(
            db,
            email="other@example.com",
            display_name="二号",
            password="Str0ng-Enough!",
        )
        raised = False
    except SetupError as exc:
        raised = True
        assert exc.status_code == 409
    assert raised
    db.close()


def test_rejects_weak_password(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr(
        "app.services.setup.get_min_password_length", lambda _db: 8
    )
    try:
        complete_initial_admin(
            db,
            email="admin@example.com",
            display_name="站长",
            password="123456",
        )
        raised = False
    except SetupError:
        raised = True
    assert raised
    assert needs_setup(db) is True
    db.close()


def test_setup_complete_cache_sticky() -> None:
    reset_setup_complete_for_tests()
    assert is_setup_complete_cached() is False
    mark_setup_complete()
    assert is_setup_complete_cached() is True
    reset_setup_complete_for_tests()
    assert is_setup_complete_cached() is False


def test_marker_without_admin_keeps_wizard_closed(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr("app.services.setup.get_min_password_length", lambda _db: 8)
    db.add(SystemConfig(key=SETUP_COMPLETED_KEY, value="1"))
    db.commit()
    assert needs_setup(db) is True
    assert setup_open(db) is False
    with pytest.raises(SetupError) as exc:
        complete_initial_admin(
            db,
            email="late@example.com",
            display_name="后来者",
            password="Str0ng-Enough!",
        )
    assert exc.value.status_code == 409
    assert db.query(User).count() == 0
    db.close()


def test_rejects_markup_in_display_name(monkeypatch) -> None:
    db = _session()
    monkeypatch.setattr("app.services.setup.get_min_password_length", lambda _db: 8)
    with pytest.raises(SetupError) as exc:
        complete_initial_admin(
            db,
            email="admin@example.com",
            display_name="<img src=x onerror=alert(1)>",
            password="Str0ng-Enough!",
        )
    assert "<" in exc.value.message
    assert needs_setup(db) is True
    db.close()


@pytest.fixture
def install_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_INSTALL_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    delete_setup_token()
    get_settings.cache_clear()


def test_setup_token_written_privately_and_logged_by_path_only(install_dir, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="zhange.setup"):
        path = ensure_setup_token()
    token = read_setup_token()
    assert path.is_relative_to(install_dir)
    assert len(token) >= 24
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert str(path) in caplog.text
    assert token not in caplog.text

    ensure_setup_token()
    assert read_setup_token() == token


def test_setup_token_matching_and_deletion(install_dir) -> None:
    ensure_setup_token()
    token = read_setup_token()
    assert setup_token_matches(token)
    assert setup_token_matches(f"  {token}\n")
    assert not setup_token_matches(token[:-1] + ("A" if token[-1] != "A" else "B"))
    assert not setup_token_matches("")
    assert not setup_token_matches(None)
    delete_setup_token()
    assert read_setup_token() == ""
    assert not setup_token_matches(token)
