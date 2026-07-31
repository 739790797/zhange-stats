"""邮箱 SMTP 配置：数据库优先，.env 兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.models.system_config import SystemConfig

EMAIL_CONFIG_KEY = "email_smtp"


def _encryption_from_legacy(use_ssl: bool, starttls: bool) -> str:
    if use_ssl:
        return "SSL"
    if starttls:
        return "STARTTLS"
    return "NONE"


def _env_defaults() -> dict[str, Any]:
    s = get_settings()
    return {
        "enabled": bool(s.SMTP_HOST and s.SMTP_FROM),
        "smtp_user": s.SMTP_USER or "",
        "smtp_from": s.SMTP_FROM or "",
        "smtp_password": s.SMTP_PASSWORD or "",
        "display_name": "",
        "smtp_host": s.SMTP_HOST or "",
        "smtp_port": int(s.SMTP_PORT or 465),
        "encryption": _encryption_from_legacy(bool(s.SMTP_USE_SSL), bool(s.SMTP_STARTTLS)),
        "code_expire_minutes": int(s.EMAIL_CODE_EXPIRE_MINUTES),
    }


def _normalize(cfg: dict[str, Any]) -> dict[str, Any]:
    """兼容旧字段 smtp_use_ssl / smtp_starttls。"""
    out = dict(cfg)
    if "encryption" not in out or not out.get("encryption"):
        out["encryption"] = _encryption_from_legacy(
            bool(out.get("smtp_use_ssl", True)),
            bool(out.get("smtp_starttls", False)),
        )
    enc = str(out["encryption"]).upper()
    if enc not in {"SSL", "STARTTLS", "NONE"}:
        enc = "SSL"
    out["encryption"] = enc
    out["enabled"] = bool(out.get("enabled", False))
    out["display_name"] = str(out.get("display_name") or "")
    out["smtp_user"] = str(out.get("smtp_user") or "")
    out["smtp_from"] = str(out.get("smtp_from") or "")
    out["smtp_host"] = str(out.get("smtp_host") or "")
    out["smtp_port"] = int(out.get("smtp_port") or 465)
    out["smtp_password"] = decrypt_secret(str(out.get("smtp_password") or ""))
    out["code_expire_minutes"] = max(1, int(out.get("code_expire_minutes") or 15))
    return out


def load_email_config(db: Session) -> dict[str, Any]:
    base = _normalize(_env_defaults())
    row = db.query(SystemConfig).filter(SystemConfig.key == EMAIL_CONFIG_KEY).first()
    if not row:
        return base
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return base
    if not isinstance(stored, dict):
        return base
    # 先取出密文再 merge，避免 _normalize 对已加密串误处理前丢失
    stored_password = stored.get("smtp_password")
    merged = {**base, **{k: v for k, v in stored.items() if v is not None}}
    if stored_password is not None and str(stored_password).strip():
        merged["smtp_password"] = decrypt_secret(str(stored_password))
    elif not str(merged.get("smtp_password") or "").strip():
        merged["smtp_password"] = base.get("smtp_password") or ""
    return _normalize(merged)


def save_email_config(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    current = load_email_config(db)
    password = payload.get("smtp_password")
    if password is None or str(password).strip() == "":
        password = current.get("smtp_password") or ""

    enc = str(payload.get("encryption") or "SSL").upper()
    if enc not in {"SSL", "STARTTLS", "NONE"}:
        enc = "SSL"

    data = _normalize(
        {
            "enabled": bool(payload.get("enabled", False)),
            "smtp_user": str(payload.get("smtp_user") or "").strip(),
            "smtp_from": str(payload.get("smtp_from") or "").strip(),
            "smtp_password": str(password),
            "display_name": str(payload.get("display_name") or "").strip(),
            "smtp_host": str(payload.get("smtp_host") or "").strip(),
            "smtp_port": int(payload.get("smtp_port") or 465),
            "encryption": enc,
            "code_expire_minutes": int(
                payload.get("code_expire_minutes")
                or current.get("code_expire_minutes")
                or 15
            ),
        }
    )

    to_store = dict(data)
    to_store["smtp_password"] = encrypt_secret(str(data.get("smtp_password") or ""))

    row = db.query(SystemConfig).filter(SystemConfig.key == EMAIL_CONFIG_KEY).first()
    raw = json.dumps(to_store, ensure_ascii=False)
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=EMAIL_CONFIG_KEY, value=raw))
    db.commit()
    return data


def resolve_mail_from(cfg: dict[str, Any]) -> str:
    """发信地址为空时回退到用户名。"""
    mail_from = (cfg.get("smtp_from") or "").strip()
    if mail_from:
        return mail_from
    return (cfg.get("smtp_user") or "").strip()


def public_email_config(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = _normalize(cfg)
    pwd = str(cfg.get("smtp_password") or "")
    mail_from = resolve_mail_from(cfg)
    return {
        "enabled": bool(cfg.get("enabled")),
        "smtp_user": cfg.get("smtp_user") or "",
        "smtp_from": cfg.get("smtp_from") or "",
        "smtp_password_set": bool(pwd),
        "display_name": cfg.get("display_name") or "",
        "smtp_host": cfg.get("smtp_host") or "",
        "smtp_port": int(cfg.get("smtp_port") or 465),
        "encryption": cfg.get("encryption") or "SSL",
        "configured": bool(
            cfg.get("enabled") and cfg.get("smtp_host") and mail_from and pwd
        ),
    }
