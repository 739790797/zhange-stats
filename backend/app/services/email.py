"""发送邮箱验证码与账号提醒信；未配置 SMTP 时默认拒绝（可开 ALLOW_EMAIL_CODE_LOG 仅本地调试）。"""

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
    code_expire_minutes,
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

# 日志里这封信的叫法：(内容, 邮件)
_LABELS = {"code": ("验证码", "验证邮件"), "notice": ("提醒", "提醒邮件")}

# 已注册 / 未注册邮箱走同一条路、各收一封信，接口响应完全一样；提醒信里不带验证码
NOTICE_ALREADY_REGISTERED = "already_registered"
NOTICE_NO_ACCOUNT_RESET = "no_account_reset"
NOTICE_BIND_TAKEN = "bind_taken"
NOTICE_QQ_LINKED = "qq_linked"

_NOTICES: dict[str, tuple[str, str]] = {
    NOTICE_ALREADY_REGISTERED: (
        "战鸽数据 · 注册提醒",
        "有人用这个邮箱申请注册战鸽数据，但该邮箱已经有账号了，无需重复注册。\n\n"
        "可直接登录；忘记密码请在登录页使用「找回密码」。如非本人操作请忽略。",
    ),
    NOTICE_NO_ACCOUNT_RESET: (
        "战鸽数据 · 找回密码",
        "有人用这个邮箱申请找回战鸽数据的密码，但该邮箱还没有可找回的账号"
        "（未注册或未完成邮箱验证）。\n\n"
        "如需使用请先注册。如非本人操作请忽略。",
    ),
    NOTICE_BIND_TAKEN: (
        "战鸽数据 · 绑定邮箱提醒",
        "有人想把这个邮箱绑定到另一个战鸽数据账号，但该邮箱已属于一个账号，未做任何改动。\n\n"
        "如果是你本人在用 QQ 登录的新账号操作，可在「完善账号」里选「绑已有账号」，"
        "用该邮箱和密码把 QQ 合并过来。如非本人操作请忽略。",
    ),
    NOTICE_QQ_LINKED: (
        "战鸽数据 · 账号安全提醒",
        "你的战鸽数据账号刚刚绑定了一个 QQ，之后可以用这个 QQ 直接登录。\n\n"
        "如非本人操作，请立即修改密码，并在个人中心解绑该 QQ。",
    ),
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
    logger.debug("邮件未发出 mode=%s to=%s purpose=%s", mode, masked_to, purpose)
    return {"sent": False, "mode": mode}


def _purpose_label(purpose: str) -> str:
    return _PURPOSE_LABEL.get((purpose or "").strip().lower(), "邮箱")


def email_delivery_mode(cfg: dict) -> str:
    """只看配置、不连 SMTP，预判这次会怎么投递：smtp / log / unavailable / smtp_error（拒发明文口令）。"""
    host = (cfg.get("smtp_host") or "").strip()
    if not cfg.get("enabled") or not host or not resolve_mail_from(cfg):
        settings = get_settings()
        # 生产环境即使误开 ALLOW_EMAIL_CODE_LOG 也不输出明文验证码
        if settings.ALLOW_EMAIL_CODE_LOG and not settings.is_production:
            return "log"
        return "unavailable"
    if plaintext_auth_error(host, str(cfg.get("encryption") or "SSL").upper()):
        return "smtp_error"
    return "smtp"


def _log_undeliverable(cfg: dict, mode: str, category: str) -> None:
    what, mail = _LABELS[category]
    if mode == "unavailable":
        log_until_change(
            logger,
            "email.unavailable",
            "邮件未配置且未开启 ALLOW_EMAIL_CODE_LOG，无法发送%s",
            what,
        )
        return
    host = (cfg.get("smtp_host") or "").strip()
    port = int(cfg.get("smtp_port") or 465)
    encryption = str(cfg.get("encryption") or "SSL").upper()
    log_until_change(
        logger,
        "email.plaintext_auth",
        "拒绝发送%s host=%s port=%s encryption=%s：%s",
        mail,
        host,
        port,
        encryption,
        plaintext_auth_error(host, encryption),
    )


def precheck_email_delivery(cfg: dict) -> str:
    """发验证码前、查邮箱是否已注册前调用：发不出去时同样按故障类型记 WARNING。"""
    mode = email_delivery_mode(cfg)
    if mode in ("unavailable", "smtp_error"):
        _log_undeliverable(cfg, mode, "code")
    return mode


def _send_with_config(
    cfg: dict,
    to_email: str,
    code: str,
    *,
    purpose: str = "register",
) -> dict:
    label = _purpose_label(purpose)
    body = (
        f"您的{label}验证码是：{code}\n\n"
        f"有效期 {code_expire_minutes(cfg)} 分钟。"
        "如非本人操作请忽略。"
    )
    return _deliver(
        cfg,
        to_email,
        subject="战鸽数据 · 邮箱验证码",
        body=body,
        purpose=purpose,
        category="code",
        dev_text=code,
    )


def _deliver(
    cfg: dict,
    to_email: str,
    *,
    subject: str,
    body: str,
    purpose: str,
    category: str,
    dev_text: str,
) -> dict:
    what, mail = _LABELS[category]
    masked_to = _mask_email(to_email)
    mode = email_delivery_mode(cfg)
    if mode == "log":
        logger.warning(
            "[email-dev] 邮件未启用或未配置，%s发给 %s → %s",
            what,
            masked_to,
            dev_text,
        )
        print(f"[战鸽数据] 邮箱{what} {to_email}: {dev_text}", flush=True)
        return {"sent": False, "mode": "log"}
    if mode != "smtp":
        _log_undeliverable(cfg, mode, category)
        return _not_sent(mode, masked_to, purpose)

    host = (cfg.get("smtp_host") or "").strip()
    mail_from = resolve_mail_from(cfg)
    password = str(cfg.get("smtp_password") or "")
    port = int(cfg.get("smtp_port") or 465)
    encryption = str(cfg.get("encryption") or "SSL").upper()

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
            "发送%s失败 host=%s port=%s encryption=%s error=%s",
            mail,
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


def send_notice_email(to_email: str, kind: str, db: Session | None = None) -> dict:
    """发账号提醒信（不带验证码）；返回值同 send_verification_email。"""
    subject, body = _NOTICES[kind]
    return _deliver(
        load_email_config(db),
        to_email,
        subject=subject,
        body=body,
        purpose=kind,
        category="notice",
        dev_text=subject,
    )


def notify_account_event(to_email: str | None, kind: str) -> None:
    """尽力而为的账号安全提醒（放 BackgroundTasks 里跑）：发不出去只记日志，不影响业务。"""
    if not to_email:
        return
    try:
        cfg = load_email_config(None)
        if email_delivery_mode(cfg) == "unavailable":
            # 站点没配邮件就没法提醒，不算故障
            logger.debug("账号提醒邮件跳过（邮件未配置） kind=%s", kind)
            return
        send_notice_email(to_email, kind)
    except Exception as exc:  # noqa: BLE001
        logger.warning("账号提醒邮件发送异常 kind=%s error=%s", kind, type(exc).__name__)
