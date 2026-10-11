"""弱口令体检：有管理员时检查；无管理员等待向导（并备好安装令牌）。"""

import pytest

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.system_config import SystemConfig
from app.models.user import User, UserRole
from app.services.password_policy import PasswordPolicyError, is_weak_password, validate_password
from app.services.security_bootstrap import check_admin_password_health
from app.services.setup import delete_setup_token, ensure_setup_token, read_setup_token


@pytest.fixture(autouse=True)
def _tmp_install(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_INSTALL_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    delete_setup_token()
    get_settings.cache_clear()


def test_validate_password_rejects_short() -> None:
    try:
        validate_password("short", min_length=8)
        raised = False
    except PasswordPolicyError:
        raised = True
    assert raised


def test_is_weak_common() -> None:
    assert is_weak_password("123456")
    assert is_weak_password("goodpass1", username="goodpass1")
    assert not is_weak_password("Str0ng-Enough!")


class _NoAdminQuery:
    def filter(self, *_a, **_k):
        return self

    def count(self):
        return 0

    def all(self):
        return []


class _NoAdminSession:
    def __init__(self, *, marker: bool = False) -> None:
        self._marker = marker

    def query(self, *_a, **_k):
        return _NoAdminQuery()

    def get(self, model, key):
        if model is SystemConfig and self._marker:
            return SystemConfig(key=key, value="1")
        return None


def test_no_admin_awaits_setup(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    # 无管理员：不因生产环境抛错，并备好安装令牌
    check_admin_password_health(_NoAdminSession())  # type: ignore[arg-type]
    assert read_setup_token()


def test_marker_without_admin_does_not_reopen_wizard() -> None:
    check_admin_password_health(_NoAdminSession(marker=True))  # type: ignore[arg-type]
    assert read_setup_token() == ""


def test_check_rejects_weak_admin_in_db(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REJECT_WEAK_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    admin = User(
        id=1,
        username="admin",
        email="a@b.c",
        display_name="管理员",
        password_hash=hash_password("123456"),
        role=UserRole.admin,
        email_verified=True,
    )

    class _Q:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def all(self):
            return self._rows

        def count(self):
            return len(self._rows)

        def first(self):
            return None

    class DummySession:
        def query(self, model):
            name = getattr(model, "__name__", "")
            if name == "SystemConfig":
                return _Q([])
            return _Q([admin])

    ensure_setup_token()
    try:
        check_admin_password_health(DummySession())  # type: ignore[arg-type]
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "弱口令" in str(exc)
    finally:
        get_settings.cache_clear()
    assert raised
    # 已有管理员：残留的安装令牌一并删掉
    assert read_setup_token() == ""
