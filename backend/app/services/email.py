"""发送邮箱验证码；未配置 SMTP 时默认拒绝（可开 ALLOW_EMAIL_CODE_LOG 仅本地调试）。"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.email_config import (
    load_email_config,
    plaintext_auth_error,
    resolve_mail_from,
)

logger = logging.getLogger(__name__)

# 公开接口每次请求都会走到这里：WARNING 按故障类型去重，任一次发送成功全部清掉
_LOG_KEYS = ("email.unavailable", "email.plaintext_auth", "email.smtp_error")

_PURPOSE_LABEL = {
    "register": "注册",
    "bind": "绑定邮箱",
    "reset": "找回密码",
    "delete": "注销账号",
    "admin_stepup": "管理员确认",
}


def _mask_email(addr: str) -> str:
    """日志里的收件人只留首字符与域名：a***@example.com。"""
    local, sep, domain = (addr or "").strip().rpartition("@")
    if not sep:
        return "***"
    return f"{local[:1]}***@{domain}"


def _failure_label(exc: BaseException) -> str:
    """SMTPRecipientsRefused 的文本带完整收件人，服务器回显也可能带，所以 SMTP 应答只留状态码。"""
    name = type(exc).__name__
    if isinstance(exc, smtplib.SMTPResponseException):
        return f"{name} {exc.smtp_code}"
    if isinstance(exc, smtplib.SMTPRecipientsRefused) or not isinstance(exc, OSError):
        return name
    return f"{name}: {exc}"[:200]


def _not_sent(mode: str, masked_to: str, purpose: str) -> dict:
    logger.debug("验证码邮件未发出 mode=%s to=%s purpose=%s", mode, masked_to, purpose)
    return {"sent": False, "mode": mode}


def _purpose_label(purpose: str) -> str:
    return _PURPOSE_LABEL.get((purpose or "").strip().lower(), "邮箱")


def _send_with_config(
    cfg: dict,
    to_email: str,
    code: str,
    *,
    purpose: str = "register",
) -> dict:
    expire = int(cfg.get("code_expire_minutes") or 15)
    label = _purpose_label(purpose)
    subject = "战鸽数据 · 邮箱验证码"
    body = (
        f"您的{label}验证码是：{code}\n\n"
        f"有效期 {expire} 分钟。"
        "如非本人操作请忽略。"
    )

    enabled = bool(cfg.get("enabled"))
    host = (cfg.get("smtp_host") or "").strip()
    mail_from = resolve_mail_from(cfg)
    password = str(cfg.get("smtp_password") or "")
    masked_to = _mask_email(to_email)

    if not enabled or not host or not mail_from:
        settings = get_settings()
        # 生产环境即使误开 ALLOW_EMAIL_CODE_LOG 也不输出明文验证码
        if settings.ALLOW_EMAIL_CODE_LOG and not settings.is_production:
            logger.warning(
                "[email-dev] 邮件未启用或未配置，验证码发给 %s → %s",
                masked_to,
                code,
            )
            print(f"[战鸽数据] 邮箱验证码 {to_email}: {code}", flush=True)
            return {"sent": False, "mode": "log"}
        log_until_change(
            logger,
            "email.unavailable",
            "邮件未配置且未开启 ALLOW_EMAIL_CODE_LOG，无法发送验证码",
        )
        return _not_sent("unavailable", masked_to, purpose)

    port = int(cfg.get("smtp_port") or 465)
    encryption = str(cfg.get("encryption") or "SSL").upper()
    refused = plaintext_auth_error(host, encryption)
    if refused:
        log_until_change(
            logger,
            "email.plaintext_auth",
            "拒绝发送验证邮件 host=%s port=%s encryption=%s：%s",
            host,
            port,
            encryption,
            refused,
        )
        return _not_sent("smtp_error", masked_to, purpose)

    display_name = (cfg.get("display_name") or "").strip()
    from_header = formataddr((display_name, mail_from)) if display_name else mail_from

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.set_content(body)

    user = (cfg.get("smtp_user") or "").strip() or mail_from

    try:
        if encryption == "SSL":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                if encryption == "STARTTLS":
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        log_until_change(
            logger,
            "email.smtp_error",
            "发送验证邮件失败 host=%s port=%s encryption=%s error=%s",
            host,
            port,
            encryption,
            _failure_label(exc),
        )
        return _not_sent("smtp_error", masked_to, purpose)
    for key in _LOG_KEYS:
        clear_log_until_change(key)
    return {"sent": True, "mode": "smtp"}


def send_verification_email(
    to_email: str,
    code: str,
    db: Session | None = None,
    *,
    purpose: str = "register",
) -> dict:
    """
    发送验证码。
    返回 {"sent": bool, "mode": "smtp"|"log"|"unavailable"|"smtp_error"}
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        cfg = load_email_config(db)
        return _send_with_config(cfg, to_email, code, purpose=purpose)
    finally:
        if own_session:
            db.close()
