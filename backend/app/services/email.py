"""发送邮箱验证码；未配置 SMTP 时默认拒绝（可开 ALLOW_EMAIL_CODE_LOG 仅本地调试）。"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.email_config import load_email_config, resolve_mail_from

logger = logging.getLogger(__name__)

_PURPOSE_LABEL = {
    "register": "注册",
    "bind": "绑定邮箱",
    "reset": "找回密码",
}


def _mask_code(code: str) -> str:
    raw = code or ""
    if len(raw) <= 2:
        return "*" * len(raw)
    return ("*" * (len(raw) - 2)) + raw[-2:]


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

    if not enabled or not host or not mail_from:
        settings = get_settings()
        # 生产环境即使误开 ALLOW_EMAIL_CODE_LOG 也不输出明文验证码
        if settings.ALLOW_EMAIL_CODE_LOG and not settings.is_production:
            logger.warning(
                "[email-dev] 邮件未启用或未配置，验证码发给 %s → %s",
                to_email,
                code,
            )
            print(f"[战鸽数据] 邮箱验证码 {to_email}: {code}", flush=True)
            return {"sent": False, "mode": "log"}
        logger.warning(
            "邮件未配置且未开启 ALLOW_EMAIL_CODE_LOG，无法发送验证码 to=%s",
            to_email,
        )
        return {"sent": False, "mode": "unavailable"}

    display_name = (cfg.get("display_name") or "").strip()
    from_header = formataddr((display_name, mail_from)) if display_name else mail_from

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.set_content(body)

    port = int(cfg.get("smtp_port") or 465)
    user = (cfg.get("smtp_user") or "").strip() or mail_from
    encryption = str(cfg.get("encryption") or "SSL").upper()

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
        return {"sent": True, "mode": "smtp"}
    except Exception:  # noqa: BLE001
        logger.exception("发送验证邮件失败")
        logger.warning(
            "[email-fallback] %s → %s（已脱敏）", to_email, _mask_code(code)
        )
        return {"sent": False, "mode": "log"}


def send_verification_email(
    to_email: str,
    code: str,
    db: Session | None = None,
    *,
    purpose: str = "register",
) -> dict:
    """
    发送验证码。
    返回 {"sent": bool, "mode": "smtp"|"log"|"unavailable"}
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
