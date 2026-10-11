"""首次安装：无管理员时走向导创建首位管理员。"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
import string
import tempfile
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.security import (
    DISPLAY_NAME_MARKUP_ERROR,
    create_user_access_token,
    has_markup_chars,
    hash_password,
)
from app.models.system_config import SystemConfig
from app.models.user import User, UserRole
from app.services.auth_config import get_min_password_length
from app.services.member_sync import ensure_user_member
from app.services.password_policy import PasswordPolicyError, validate_password

logger = logging.getLogger("zhange.setup")

SETUP_COMPLETED_KEY = "setup_completed"
SETUP_TOKEN_FILENAME = "setup-token"
SETUP_TOKEN_HEADER = "X-Setup-Token"

_setup_done = False
_setup_lock = threading.Lock()
_token_lock = threading.Lock()
_token_announced = False


def is_setup_complete_cached() -> bool:
    return _setup_done


def mark_setup_complete() -> None:
    global _setup_done
    with _setup_lock:
        _setup_done = True


def reset_setup_complete_for_tests() -> None:
    global _setup_done
    with _setup_lock:
        _setup_done = False


class SetupError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def needs_setup(db: Session) -> bool:
    return db.query(User).filter(User.role == UserRole.admin).count() == 0


def setup_marker_exists(db: Session) -> bool:
    return db.get(SystemConfig, SETUP_COMPLETED_KEY) is not None


def setup_open(db: Session) -> bool:
    """还能走向导建首位管理员：既没有管理员，也从未写过完成标记。"""
    return needs_setup(db) and not setup_marker_exists(db)


def setup_token_path() -> Path:
    from app.core.config import get_settings

    return get_settings().data_dir_path / SETUP_TOKEN_FILENAME


def read_setup_token() -> str:
    try:
        return setup_token_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_private_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp 建出来就是 0600；replace 保证读者不会读到半个文件
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ensure_setup_token() -> Path:
    """向导未完成时保证令牌文件存在。日志只给路径，令牌本身只在文件里。"""
    global _token_announced
    path = setup_token_path()
    with _token_lock:
        if not read_setup_token():
            _write_private_file(path, (secrets.token_urlsafe(24) + "\n").encode("ascii"))
            _token_announced = False
        if not _token_announced:
            _token_announced = True
            logger.warning(
                "setup: install token is in %s; enter it in the setup wizard "
                "(deleted once setup completes)",
                path,
            )
    return path


def setup_token_matches(provided: str | None) -> bool:
    expected = read_setup_token()
    given = (provided or "").strip()
    if not expected or not given:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), given.encode("utf-8"))


def delete_setup_token() -> None:
    global _token_announced
    path = setup_token_path()
    with _token_lock:
        _token_announced = False
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning("setup: could not delete install token %s (%s)", path, exc)


def snapshot_database_settings() -> bytes | None:
    """向导写连接设置前 config/database.json 的原样内容；None 表示原来没有这个文件。"""
    from app.core.file_config import config_path

    try:
        return config_path("database").read_bytes()
    except FileNotFoundError:
        return None


def roll_back_database_choice(snapshot: bytes | None) -> None:
    """选库后建表失败：放回原来的 database.json 并断开那个库，否则下次启动还会去连它。"""
    from app.core.config import get_settings
    from app.core.database import get_engine
    from app.core.file_config import clear_cache, config_path

    path = config_path("database")
    try:
        if snapshot is None:
            path.unlink(missing_ok=True)
        else:
            _write_private_file(path, snapshot)
    except OSError as exc:
        logger.error("setup: could not roll back %s (%s); remove it before restarting", path, exc)
    clear_cache("database")
    get_settings.cache_clear()
    try:
        get_engine().dispose()
    except Exception:  # noqa: BLE001
        pass


def ensure_setup_marker_if_admins_exist(db: Session) -> None:
    """已有管理员的旧库：补写完成标记。"""
    if needs_setup(db):
        return
    row = db.get(SystemConfig, SETUP_COMPLETED_KEY)
    if row is None:
        db.add(SystemConfig(key=SETUP_COMPLETED_KEY, value="1"))
        db.commit()


def _unique_username(db: Session) -> str:
    alphabet = string.ascii_lowercase + string.digits
    for _ in range(20):
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        username = f"admin_{suffix}"
        if not db.query(User).filter(User.username == username).first():
            return username
    raise SetupError("无法生成唯一用户名，请重试", status_code=500)


def complete_initial_admin(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
) -> tuple[User, str]:
    """创建首位管理员并返回 (user, access_token)。已有管理员或写过完成标记即拒绝。"""
    if not setup_open(db):
        raise SetupError("系统已完成初始化", status_code=409)

    email_norm = email.strip().lower()
    name = display_name.strip()
    if not name:
        raise SetupError("请填写显示名")
    if has_markup_chars(name):
        raise SetupError(DISPLAY_NAME_MARKUP_ERROR)
    if "@" not in email_norm:
        raise SetupError("邮箱格式不正确")

    if db.query(User).filter(User.email == email_norm).first():
        raise SetupError("该邮箱已被使用")

    try:
        password_ok = validate_password(
            password,
            min_length=get_min_password_length(db),
        )
    except PasswordPolicyError as exc:
        raise SetupError(str(exc)) from exc

    user = User(
        username=_unique_username(db),
        email=email_norm,
        display_name=name[:64],
        password_hash=hash_password(password_ok),
        role=UserRole.admin,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    # 极窄竞态：若已有其他管理员，撤销本次创建
    others = (
        db.query(User)
        .filter(User.role == UserRole.admin, User.id != user.id)
        .count()
    )
    if others > 0:
        db.rollback()
        raise SetupError("系统已完成初始化", status_code=409)

    ensure_user_member(db, user)
    if db.get(SystemConfig, SETUP_COMPLETED_KEY) is None:
        db.add(SystemConfig(key=SETUP_COMPLETED_KEY, value="1"))
    db.commit()
    db.refresh(user)
    token = create_user_access_token(user)
    return user, token
