"""口令强度：公共弱口令表 + 按安全策略校验。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User, UserRole

WEAK_PASSWORDS = frozenset(
    {
        "123456",
        "password",
        "admin",
        "admin123",
        "12345678",
        "qwerty",
        "zhange",
        "zhange123",
    }
)

_DEFAULT_MIN_LENGTH = 8


class PasswordPolicyError(ValueError):
    """口令不符合策略。"""


def is_weak_password(
    password: str,
    *,
    username: str | None = None,
    min_length: int = _DEFAULT_MIN_LENGTH,
) -> bool:
    pwd = (password or "").strip()
    if not pwd or len(pwd) < max(1, int(min_length)):
        return True
    if pwd.lower() in WEAK_PASSWORDS:
        return True
    if username and pwd == username:
        return True
    return False


def validate_password(
    password: str,
    *,
    username: str | None = None,
    min_length: int = _DEFAULT_MIN_LENGTH,
) -> str:
    """返回规范化后的口令；不合规则抛 PasswordPolicyError。"""
    pwd = (password or "").strip()
    min_len = max(1, int(min_length))
    if not pwd:
        raise PasswordPolicyError("请设置密码")
    if len(pwd) < min_len:
        raise PasswordPolicyError(f"密码至少 {min_len} 位")
    if pwd.lower() in WEAK_PASSWORDS:
        raise PasswordPolicyError("密码过于简单，请更换")
    if username and pwd == username:
        raise PasswordPolicyError("密码不能与用户名相同")
    return pwd


_WEAK_HASH_CACHE: dict[str, bool] = {}


def password_matches_weak_list(
    password_hash: str,
    *,
    username: str | None = None,
) -> bool:
    """对已存哈希做弱口令字典探测（启动体检 / 显式检查用；bcrypt 很慢，勿放热路径）。"""
    cache_key = f"{password_hash}\0{username or ''}"
    cached = _WEAK_HASH_CACHE.get(cache_key)
    if cached is not None:
        return cached

    candidates = set(WEAK_PASSWORDS)
    if username:
        candidates.add(username)
    matched = False
    for candidate in candidates:
        try:
            if verify_password(candidate, password_hash):
                matched = True
                break
        except Exception:  # noqa: BLE001 — 损坏哈希等
            continue
    _WEAK_HASH_CACHE[cache_key] = matched
    return matched


def invalidate_weak_password_cache(password_hash: str | None = None) -> None:
    if not password_hash:
        _WEAK_HASH_CACHE.clear()
        return
    drop = [k for k in _WEAK_HASH_CACHE if k.startswith(f"{password_hash}\0")]
    for k in drop:
        _WEAK_HASH_CACHE.pop(k, None)


def list_admins_with_weak_password(db: Session) -> list[User]:
    weak: list[User] = []
    admins = db.query(User).filter(User.role == UserRole.admin).all()
    for user in admins:
        if not user.password_hash:
            weak.append(user)
            continue
        if password_matches_weak_list(
            user.password_hash, username=user.username
        ):
            weak.append(user)
    return weak
