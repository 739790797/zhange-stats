"""第三方集成密钥：数据库优先，.env 兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.database import SessionLocal
from app.models.system_config import SystemConfig

INTEGRATIONS_KEY = "integrations"


def _env_defaults() -> dict[str, str]:
    s = get_settings()
    return {
        "steam_api_key": (s.STEAM_API_KEY or "").strip(),
        "qq_app_id": (s.QQ_APP_ID or "").strip(),
        "qq_app_key": (s.QQ_APP_KEY or "").strip(),
    }


def load_integrations(db: Session) -> dict[str, str]:
    base = _env_defaults()
    row = db.query(SystemConfig).filter(SystemConfig.key == INTEGRATIONS_KEY).first()
    if not row:
        return dict(base)
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return dict(base)
    if not isinstance(stored, dict):
        return dict(base)

    merged = dict(base)
    if "qq_app_id" in stored and stored["qq_app_id"] is not None:
        merged["qq_app_id"] = str(stored["qq_app_id"] or "").strip()

    for secret_key in ("steam_api_key", "qq_app_key"):
        if secret_key not in stored:
            continue
        raw = stored.get(secret_key)
        if raw is None:
            # 显式 null：删除覆盖，回落 env（已在 base）
            continue
        text = str(raw or "").strip()
        if not text:
            # 空串：同样视为未在库中配置 → 回落 env
            continue
        merged[secret_key] = decrypt_secret(text).strip()

    return {
        "steam_api_key": merged.get("steam_api_key") or "",
        "qq_app_id": merged.get("qq_app_id") or "",
        "qq_app_key": merged.get("qq_app_key") or "",
    }


def save_integrations(db: Session, payload: dict[str, Any]) -> dict[str, str]:
    row = db.query(SystemConfig).filter(SystemConfig.key == INTEGRATIONS_KEY).first()
    stored: dict[str, Any] = {}
    if row:
        try:
            parsed = json.loads(row.value or "{}")
            if isinstance(parsed, dict):
                stored = parsed
        except json.JSONDecodeError:
            stored = {}

    # qq_app_id：明文，始终可写
    if "qq_app_id" in payload and payload.get("qq_app_id") is not None:
        stored["qq_app_id"] = str(payload.get("qq_app_id") or "").strip()

    if payload.get("clear_steam_api_key"):
        stored.pop("steam_api_key", None)
    else:
        steam_key = payload.get("steam_api_key")
        if steam_key is not None and str(steam_key).strip():
            stored["steam_api_key"] = encrypt_secret(str(steam_key).strip())

    if payload.get("clear_qq_app_key"):
        stored.pop("qq_app_key", None)
    else:
        qq_key = payload.get("qq_app_key")
        if qq_key is not None and str(qq_key).strip():
            stored["qq_app_key"] = encrypt_secret(str(qq_key).strip())

    raw = json.dumps(stored, ensure_ascii=False)
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=INTEGRATIONS_KEY, value=raw))
    db.commit()
    return load_integrations(db)


def public_integrations(cfg: dict[str, str]) -> dict[str, Any]:
    steam = cfg.get("steam_api_key") or ""
    qq_key = cfg.get("qq_app_key") or ""
    qq_id = cfg.get("qq_app_id") or ""
    return {
        "steam_api_key": steam,
        "steam_api_key_set": bool(steam),
        "qq_app_id": qq_id,
        "qq_app_key": qq_key,
        "qq_app_key_set": bool(qq_key),
        "qq_configured": bool(qq_id and qq_key),
        "steam_configured": bool(steam),
    }


def get_steam_api_key(db: Session | None = None) -> str:
    if db is not None:
        return load_integrations(db).get("steam_api_key") or ""
    session = SessionLocal()
    try:
        return load_integrations(session).get("steam_api_key") or ""
    finally:
        session.close()


def get_qq_credentials(db: Session | None = None) -> tuple[str, str]:
    def _read(session: Session) -> tuple[str, str]:
        cfg = load_integrations(session)
        return cfg.get("qq_app_id") or "", cfg.get("qq_app_key") or ""

    if db is not None:
        return _read(db)
    session = SessionLocal()
    try:
        return _read(session)
    finally:
        session.close()
