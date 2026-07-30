"""发送注册验证码邮件；未配置 / 未启用 SMTP 时写入日志。"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.email_config import load_email_config, resolve_mail_from

logger = logging.getLogger(__name__)


def _send_with_config(cfg: dict, to_email: str, code: str) -> dict:
    expire = int(cfg.get("code_expire_minutes") or 15)
    subject = "战鸽数据 · 邮箱验证码"
    body = (
        f"您的注册验证码是：{code}\n\n"
        f"有效期 {expire} 分钟。"
        "如非本人操作请忽略。"
    )

    enabled = bool(cfg.get("enabled"))
    host = (cfg.get("smtp_host") or "").strip()
    mail_from = resolve_mail_from(cfg)
    password = str(cfg.get("smtp_password") or "")

    if not enabled or not host or not mail_from:
        logger.warning(
            "[email-dev] 邮件未启用或未配置，验证码发给 %s → %s", to_email, code
        )
        print(f"[战鸽数据] 邮箱验证码 {to_email}: {code}", flush=True)
        return {"sent": False, "mode": "log"}

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
        logger.warning("[email-fallback] %s → %s", to_email, code)
        print(f"[战鸽数据] 邮件发送失败，验证码 {to_email}: {code}", flush=True)
        return {"sent": False, "mode": "log"}


def send_verification_email(
    to_email: str, code: str, db: Session | None = None
) -> dict:
    """
    发送验证码。
    返回 {"sent": bool, "mode": "smtp"|"log"}
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        cfg = load_email_config(db)
        return _send_with_config(cfg, to_email, code)
    finally:
        if own_session:
            db.close()
