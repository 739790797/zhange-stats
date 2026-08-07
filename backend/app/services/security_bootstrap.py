"""启动时安全体检：弱口令、生产环境危险开关等。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.auth_config import (
    effective_reject_weak_admin_password,
    load_auth_config,
)
from app.services.password_policy import list_admins_with_weak_password
from app.services.setup import needs_setup

logger = logging.getLogger("zhange.security")


def check_email_code_log_policy() -> None:
    """生产环境禁止 ALLOW_EMAIL_CODE_LOG（明文验证码进日志/stdout）。"""
    settings = get_settings()
    if settings.is_production and settings.ALLOW_EMAIL_CODE_LOG:
        raise RuntimeError(
            "生产环境禁止 ALLOW_EMAIL_CODE_LOG=true（验证码会写入日志）。"
            "请关闭该开关并配置 SMTP。"
        )


def warn_if_weak_admin_password(db: Session | None = None) -> None:
    """兼容旧入口：优先连库体检。"""
    if db is None:
        from app.core.database import SessionLocal

        try:
            session = SessionLocal()
        except Exception:  # noqa: BLE001
            return
        try:
            check_admin_password_health(session)
        finally:
            session.close()
        return
    check_admin_password_health(db)


def check_admin_password_health(db: Session) -> None:
    if needs_setup(db):
        logger.info("尚未初始化管理员，请打开站点完成安装向导")
        return

    cfg = load_auth_config(db)
    reject = effective_reject_weak_admin_password(cfg)
    weak_admins = list_admins_with_weak_password(db)
    if not weak_admins:
        return

    names = ", ".join(
        (u.display_name or u.username or str(u.id)) for u in weak_admins
    )
    msg = (
        f"检测到管理员弱口令：{names}。"
        "请在「安全设置」中修改密码，或到用户管理重置。"
    )
    if reject:
        raise RuntimeError(msg)
    logger.warning(msg)
