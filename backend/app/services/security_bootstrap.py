"""启动时检测弱管理员口令。"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger("zhange.security")

_WEAK_PASSWORDS = frozenset(
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


def warn_if_weak_admin_password() -> None:
    settings = get_settings()
    pwd = (settings.ADMIN_PASSWORD or "").strip()
    weak = (
        not pwd
        or len(pwd) < 8
        or pwd.lower() in _WEAK_PASSWORDS
        or pwd == settings.ADMIN_USERNAME
    )
    if not weak:
        return
    msg = (
        "检测到弱管理员口令（ADMIN_PASSWORD）。请在 .env 中改为至少 8 位的强密码；"
        "若仅更新已有库中的管理员密码，可设 RESET_ADMIN_PASSWORD=true 后重启一次。"
    )
    if settings.reject_weak_admin_password:
        raise RuntimeError(msg)
    logger.warning(msg)
