"""安装向导：无管理员时创建首位管理员。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import verify_password
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.user import User, UserRole
from app.models.member import Member  # noqa: F401
from app.services.setup import SetupError, complete_initial_admin, needs_setup


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
        "app.services.setup.create_access_token", lambda _u: "tok"
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
