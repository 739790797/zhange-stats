"""启动时安全体检：弱口令、生产环境危险开关等。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.services.auth_config import (
    effective_reject_weak_admin_password,
    load_auth_config,
)
from app.services.password_policy import list_admins_with_weak_password
from app.services.setup import (
    delete_setup_token,
    ensure_setup_token,
    needs_setup,
    setup_marker_exists,
)

logger = logging.getLogger("zhange.security")

_EMAIL_CODE_LOG_REFUSAL = (
    "生产环境禁止 ALLOW_EMAIL_CODE_LOG=true（验证码会写入日志）。"
    "请关闭该开关并配置 SMTP。"
)


def _weak_admin_message(weak_admins: list[User]) -> str:
    names = ", ".join(
        (u.display_name or u.username or str(u.id)) for u in weak_admins
    )
    return (
        f"检测到管理员弱口令：{names}。"
        "请在「安全设置」中修改密码，或到用户管理重置。"
    )


def check_email_code_log_policy() -> None:
    """生产环境禁止 ALLOW_EMAIL_CODE_LOG（明文验证码进日志/stdout）。"""
    settings = get_settings()
    if settings.is_production and settings.ALLOW_EMAIL_CODE_LOG:
        raise RuntimeError(_EMAIL_CODE_LOG_REFUSAL)


def check_admin_password_health(db: Session) -> None:
    if needs_setup(db):
        if setup_marker_exists(db):
            logger.warning(
                "已完成过初始化但当前没有管理员；安装向导不会再开放，恢复步骤见 docs/security.md"
            )
            return
        logger.info("尚未初始化管理员，请打开站点完成安装向导")
        try:
            ensure_setup_token()
        except OSError:
            logger.warning("无法写入安装令牌文件，安装向导将无法提交", exc_info=True)
        return
    delete_setup_token()

    cfg = load_auth_config(db)
    reject = effective_reject_weak_admin_password(cfg)
    weak_admins = list_admins_with_weak_password(db)
    if not weak_admins:
        return

    msg = _weak_admin_message(weak_admins)
    if reject:
        raise RuntimeError(msg)
    logger.warning(msg)


def production_preflight_problems(db: Session) -> list[str]:
    """按 APP_ENV=production 口径跑上面两项启动体检，返回会让重启失败的原因；空列表表示可以切。"""
    problems: list[str] = []
    if get_settings().ALLOW_EMAIL_CODE_LOG:
        problems.append(_EMAIL_CODE_LOG_REFUSAL)
    if not needs_setup(db):
        cfg = load_auth_config(db)
        if effective_reject_weak_admin_password(cfg, production=True):
            weak_admins = list_admins_with_weak_password(db)
            if weak_admins:
                problems.append(_weak_admin_message(weak_admins))
    return problems
