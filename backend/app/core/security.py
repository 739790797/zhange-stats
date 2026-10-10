import functools
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.key_derivation import PURPOSE_JWT, derive_key
from app.core.timeutil import utc_now

ALGORITHM = "HS256"
# bcrypt 只吃前 72 字节；与 passlib 的静默截断一致，存量 $2b$ 哈希照常校验
_BCRYPT_MAX_BYTES = 72
# 盐不足 22 字符时 bcrypt 4.x 直接 Rust panic（BaseException），先按格式挡掉损坏的哈希
_BCRYPT_HASH = re.compile(r"\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}")
MAX_ACCESS_TOKEN_MINUTES = 60 * 24 * 30

# 显示名会进 Leaflet tooltip 等按 innerHTML 渲染的地方；前端漏一处转义就是存储型 XSS，后端干脆不收尖括号
_MARKUP_CHARS = frozenset("<>")
DISPLAY_NAME_MARKUP_ERROR = "显示名不能包含 < 或 >"


def has_markup_chars(text: str | None) -> bool:
    return any(ch in _MARKUP_CHARS for ch in (text or ""))


def strip_markup_chars(text: str | None) -> str:
    return "".join(ch for ch in (text or "") if ch not in _MARKUP_CHARS)


@dataclass(frozen=True)
class AccessPrincipal:
    """JWT 身份。`sub` 为 user_id；`token_version` 为 None 表示升级前签发、不带 `ver` 的令牌。"""

    user_id: int
    username: str | None
    token_version: int | None = None


def _password_bytes(password: str) -> bytes:
    return (password or "").encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed or not _BCRYPT_HASH.fullmatch(hashed):
        return False
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("ascii"))
    except (TypeError, ValueError):
        return False


@functools.lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def verify_login_password(plain: str, hashed: str | None) -> bool:
    """先按原样校验；旧版改密 / 重置会去掉首尾空白再存，输入带首尾空白时再试一次去空白的值。

    hashed 为空（账号不存在 / 已注销）时照样对随机哈希跑一遍 bcrypt 再返回 False，
    响应耗时与真账号输错一致，不能靠计时判断账号是否存在。
    """
    target = hashed or _dummy_password_hash()
    ok = verify_password(plain, target)
    if not ok:
        stripped = (plain or "").strip()
        if stripped and stripped != plain:
            ok = verify_password(stripped, target)
    return ok and bool(hashed)


def bump_token_version(user: Any) -> int:
    """作废该账号已签发的全部令牌（改密、重置、降级、注销、退出所有设备）。"""
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    return user.token_version


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    *,
    user_id: int,
    token_version: int = 0,
) -> str:
    from app.services.auth_config import get_access_token_expire_minutes

    settings = get_settings()
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else get_access_token_expire_minutes()
    )
    minutes = max(1, min(int(minutes), MAX_ACCESS_TOKEN_MINUTES))
    payload: dict = {
        "exp": utc_now() + timedelta(minutes=minutes),
        "sub": str(int(user_id)),
        "username": subject,
        "ver": int(token_version or 0),
    }
    return jwt.encode(
        payload, derive_key(settings.SECRET_KEY, PURPOSE_JWT), algorithm=ALGORITHM
    )


def create_user_access_token(user: Any) -> str:
    return create_access_token(
        user.username,
        user_id=user.id,
        token_version=int(getattr(user, "token_version", 0) or 0),
    )


def _decode_payload(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            derive_key(settings.SECRET_KEY, PURPOSE_JWT),
            algorithms=[ALGORITHM],
        )
    except InvalidTokenError:
        pass
    # 过渡：升级前直接用 SECRET_KEY 签的令牌，只认剩余有效期不超过新上限的，最迟一个上限周期后全部失效
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None
    if exp - utc_now().timestamp() > MAX_ACCESS_TOKEN_MINUTES * 60:
        return None
    return payload


def decode_access_token(token: str) -> AccessPrincipal | None:
    payload = _decode_payload(token)
    if payload is None:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    text = str(sub)
    if not text.isdigit():
        return None
    token_version: int | None = None
    if "ver" in payload:
        ver = payload.get("ver")
        if isinstance(ver, bool) or not isinstance(ver, int):
            return None
        token_version = ver
    username_claim = payload.get("username")
    username = str(username_claim) if username_claim else None
    return AccessPrincipal(
        user_id=int(text), username=username, token_version=token_version
    )


def token_version_matches(principal: AccessPrincipal, user: Any) -> bool:
    current = int(getattr(user, "token_version", 0) or 0)
    if principal.token_version is None:
        return current == 0
    return principal.token_version == current
